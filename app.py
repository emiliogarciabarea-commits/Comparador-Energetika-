
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador de Tarifas Eléctricas (Coste Neto)")
st.markdown("""
Esta herramienta extrae el **coste base (Potencia + Energía)** de tu factura, 
eliminando impuestos (IVA, Impuesto Eléctrico) y alquileres para que la 
comparación con otras compañías sea 100% real y justa.
""")

# --- CONFIGURACIÓN DE LA BASE DE DATOS POR DEFECTO ---
ARCHIVO_DB_POR_DEFECTO = "tarifas_companias.xlsx"

if os.path.exists(ARCHIVO_DB_POR_DEFECTO):
    try:
        df_raw = pd.read_excel(ARCHIVO_DB_POR_DEFECTO, header=1)
        st.sidebar.success(f"✅ Tarifas cargadas: {ARCHIVO_DB_POR_DEFECTO}")
    except:
        st.sidebar.error("Error al leer el archivo Excel en GitHub.")
        df_raw = None
else:
    st.sidebar.warning("⚠️ No se encontró la base de datos en el repositorio.")
    archivo_subido = st.sidebar.file_uploader("Sube tu Excel de Tarifas manualmente", type=["xlsx"])
    if archivo_subido:
        df_raw = pd.read_excel(archivo_subido, header=1)
    else:
        df_raw = None

# --- FUNCIÓN DE EXTRACCIÓN DE DATOS ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_content = pagina.extract_text()
            if texto_content:
                texto_completo += texto_content + "\n"

    # Extracción de Fecha
    match_fecha = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha_factura = match_fecha.group(1) if match_fecha else "S/D"

    # Extracción de Días (Específico para Energía XXI y Mercado Libre)
    match_dias = re.search(r"Periodo\s+de\s+consumo:.*?\((\d+)\s*días\)", texto_completo, re.IGNORECASE)
    if not match_dias:
        match_dias = re.search(r"Potencia.*?(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias_factura = int(match_dias.group(1)) if match_dias else 30

    # Extracción de Potencia Contratada
    match_potencia = re.search(r"Potencia\s+contratada.*?(\d+[.,]\d+|\d+)\s*kW", texto_completo, re.IGNORECASE)
    if not match_potencia:
        match_potencia = re.search(r"Potencia\s+P1\s*(\d+[.,]\d+|\d+)\s*kW", texto_completo, re.IGNORECASE)
    potencia_factura = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 3.3

    # Extracción de Consumos (Punta, Llano, Valle y Excedentes)
    patrones_kwh = {
        "Punta": r"(?:consumo.*?punta|Consumo\s+en\s+P1).*?(\d+[.,]?\d*)\s*kWh",
        "Llano": r"(?:consumo.*?llano|Consumo\s+en\s+P2).*?(\d+[.,]?\d*)\s*kWh",
        "Valle": r"(?:consumo.*?valle|Consumo\s+en\s+P3).*?(\d+[.,]?\d*)\s*kWh",
        "Excedentes": r"(?:Excedentes|Energía\s+vertida).*?(-?\d+[.,]?\d*)\s*kWh"
    }
    
    consumos = {}
    for k, p in patrones_kwh.items():
        match = re.search(p, texto_completo, re.IGNORECASE | re.DOTALL)
        if match:
            consumos[k] = float(match.group(1).replace(',', '.'))
        else:
            consumos[k] = 0.0

    # --- CÁLCULO DEL IMPORTE NETO (SOLO POTENCIA + ENERGÍA) ---
    # Buscamos los bloques de coste antes de impuestos
    m_pot_eur = re.search(r"(?:Por potencia contratada|Facturación por potencia).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    m_ene_eur = re.search(r"(?:Por energía consumida|Facturación por energía).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    
    coste_potencia = float(m_pot_eur.group(1).replace(',', '.')) if m_pot_eur else 0.0
    coste_energia = float(m_ene_eur.group(1).replace(',', '.')) if m_ene_eur else 0.0
    
    # El neto real es la suma de los conceptos base de la factura
    importe_neto_pdf = round(coste_potencia + coste_energia, 2)
        
    return {
        "archivo": archivo_pdf.name, 
        "fecha": fecha_factura, 
        "dias": dias_factura, 
        "potencia": potencia_factura, 
        "consumos": consumos, 
        "neto_real": importe_neto_pdf
    }

# --- INTERFAZ DE USUARIO ---
archivos_pdf = st.file_uploader("Sube tus facturas PDF", type=["pdf"], accept_multiple_files=True)

if df_raw is not None and archivos_pdf:
    # Preparar datos de tarifas del Excel
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    ranking = []

    for pdf in archivos_pdf:
        datos = extraer_datos(pdf)
        exc_kwh = abs(datos['consumos']['Excedentes'])
        
        # 1. Fila de la factura actual (Importe NETO extraído del PDF)
        ranking.append({
            "Archivo": datos['archivo'], 
            "Compañía": "🏠 ACTUAL (NETO SIN IMP.)",
            "Punta": datos['consumos']['Punta'], 
            "Llano": datos['consumos']['Llano'], 
            "Valle": datos['consumos']['Valle'],
            "TOTAL NETO (€)": datos['neto_real']
        })

        # 2. Simulación con tarifas de la base de datos
        for _, fila in df_tarifas.iterrows():
            try:
                p_pot_anual = float(fila['Pot_P1']) + float(fila['Pot_P2'])
                coste_fijo = datos['potencia'] * datos['dias'] * p_pot_anual
                coste_variable = (datos['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                                  datos['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                                  datos['consumos']['Valle'] * float(fila['Ene_Valle']))
                total_simulado = coste_fijo + coste_variable - (exc_kwh * float(fila['Precio_Exc']))
                
                ranking.append({
                    "Archivo": datos['archivo'], 
                    "Compañía": str(fila['Compania']),
                    "Punta": datos['consumos']['Punta'], 
                    "Llano": datos['consumos']['Llano'], 
                    "Valle": datos['consumos']['Valle'],
                    "TOTAL NETO (€)": round(total_simulado, 2)
                })
            except:
                continue

    # Mostrar tabla de resultados ordenada por precio
    df_final = pd.DataFrame(ranking).sort_values(by=["Archivo", "TOTAL NETO (€)"])
    st.write("### 📊 Comparativa de Costes Netos")
    st.dataframe(df_final, use_container_width=True)

    # Opción de descarga
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False)
    st.download_button("📥 Descargar reporte Excel", data=buffer.getvalue(), file_name="comparativa_neta.xlsx")

elif df_raw is None:
    st.error("Falta la base de datos de tarifas.")
else:
    st.info("Esperando facturas PDF para analizar...")
