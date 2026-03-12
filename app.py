
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador de Tarifas Eléctricas")
st.markdown("Esta app analiza tus facturas y busca la mejor compañía según tu consumo real.")

# --- CONFIGURACIÓN DE LA BASE DE DATOS POR DEFECTO ---
ARCHIVO_DB_POR_DEFECTO = "tarifas_companias.xlsx"

# Intentar cargar el archivo automáticamente
if os.path.exists(ARCHIVO_DB_POR_DEFECTO):
    df_raw = pd.read_excel(ARCHIVO_DB_POR_DEFECTO, header=1)
    st.sidebar.success(f"✅ Base de datos '{ARCHIVO_DB_POR_DEFECTO}' cargada por defecto.")
else:
    st.sidebar.warning("⚠️ No se encontró la base de datos por defecto.")
    archivo_subido = st.sidebar.file_uploader("Sube tu Excel de Tarifas manualmente", type=["xlsx"])
    if archivo_subido:
        df_raw = pd.read_excel(archivo_subido, header=1)
    else:
        df_raw = None

# --- FUNCIÓN DE EXTRACCIÓN ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_content = pagina.extract_text()
            if texto_content:
                texto_completo += texto_content + "\n"

    # Regex para Fecha
    match_fecha = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha_val = match_fecha.group(1) if match_fecha else "S/D"

    # Regex para Días
    match_dias = re.search(r"Potencia\s+P1.*?kW.*?(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias_val = int(match_dias.group(1)) if match_dias else 30

    # Regex para Potencia
    match_potencia = re.search(r"Potencia\s+P1\s*(\d+[.,]\d+|\d+)\s*kW", texto_completo, re.IGNORECASE)
    pot_val = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 4.6

    # Regex para Consumos
    patrones_kwh = {
        "Punta": r"consumo\s+electricidad\s+punta.*?(\d+)\s*kWh",
        "Llano": r"consumo\s+electricidad\s+llano.*?(\d+)\s*kWh",
        "Valle": r"consumo\s+electricidad\s+valle.*?(\d+)\s*kWh",
        "Excedentes": r"(?:Excedentes|Energía\s+vertida|Valoración\s+excedentes).*?(-?\d+)\s*kWh"
    }
    
    c = {k: (int(re.search(p, texto_completo, re.IGNORECASE | re.DOTALL).group(1)) if re.search(p, texto_completo, re.IGNORECASE | re.DOTALL) else 0) for k, p in patrones_kwh.items()}
    
    match_actual = re.search(r"(?:Total\s+importe|Total\s+factura|Electricidad).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    importe_actual = float(match_actual.group(1).replace(',', '.')) if match_actual else 0.0
        
    return {
        "archivo": archivo_pdf.name, 
        "fecha": fecha_val, 
        "dias": dias_val, 
        "potencia": pot_val, 
        "consumos": c, 
        "importe_real": importe_actual
    }

# --- INTERFAZ ---
st.header("Sube tus facturas PDF")
archivos_pdf = st.file_uploader("Selecciona uno o varios PDFs", type=["pdf"], accept_multiple_files=True)

if df_raw is not None and archivos_pdf:
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    ranking = []

    for pdf in archivos_pdf:
        d = extraer_datos(pdf)
        exc_kwh = abs(d['consumos']['Excedentes'])
        
        # Factura Real
        ranking.append({
            "Archivo": d['archivo'], "Fecha": d['fecha'], "Compañía": "🏠 ACTUAL (PDF)",
            "Punta": d['consumos']['Punta'], "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
            "Exc": exc_kwh, "TOTAL (€)": d['importe_real']
        })

        # Comparativa
        for _, fila in df_tarifas.iterrows():
            try:
                p_pot = float(fila['Pot_P1']) + float(fila['Pot_P2'])
                coste_fijo = d['potencia'] * d['dias'] * p_pot
                coste_var = (d['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                             d['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                             d['consumos']['Valle'] * float(fila['Ene_Valle']))
                total = coste_fijo + coste_var - (exc_kwh * float(fila['Precio_Exc']))
                
                ranking.append({
                    "Archivo": d['archivo'], "Fecha": d['fecha'], "Compañía": str(fila['Compania']),
                    "Punta": d['consumos']['Punta'], "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
                    "Exc": exc_kwh, "TOTAL (€)": round(total, 2)
                })
            except: continue

    df_final = pd.DataFrame(ranking).sort_values(by=["Archivo", "TOTAL (€)"])
    st.write("### 📊 Resultados de la comparativa")
    st.dataframe(df_final, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False)
    st.download_button("📥 Descargar reporte en Excel", data=buffer.getvalue(), file_name="comparativa_luz.xlsx")

elif df_raw is None:
    st.error("No hay base de datos cargada. Sube el archivo Excel en el lateral.")
else:
    st.info("Sube tus facturas PDF para ver la comparativa.")
