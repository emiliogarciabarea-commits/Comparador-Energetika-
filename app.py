
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io

st.set_page_config(page_title="Comparador Luz Solar", layout="wide")

st.title("⚡ Mi Comparador de Tarifas Eléctricas")
st.markdown("Esta app analiza tus facturas y busca la mejor compañía según tu consumo real.")

# --- FUNCIONES DE EXTRACCIÓN ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_content = pagina.extract_text()
            if texto_content:
                texto_completo += texto_content + "\n"

    # Regex para Fecha
    match_fecha = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha = match_fecha.group(1) if match_fecha else "S/D"

    # Regex para Días
    match_dias = re.search(r"Potencia\s+P1.*?kW.*?(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias = int(match_dias.group(1)) if match_dias else 30

    # Regex para Potencia
    match_potencia = re.search(r"Potencia\s+P1\s*(\d+[.,]\d+|\d+)\s*kW", texto_completo, re.IGNORECASE)
    pot = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 4.6

    # Regex para Consumos
    patrones_kwh = {
        "Punta": r"consumo\s+electricidad\s+punta.*?(\d+)\s*kWh",
        "Llano": r"consumo\s+electricidad\s+llano.*?(\d+)\s*kWh",
        "Valle": r"consumo\s+electricidad\s+valle.*?(\d+)\s*kWh",
        "Excedentes": r"(?:Excedentes|Energía\s+vertida|Valoración\s+excedentes).*?(-?\d+)\s*kWh"
    }
    
    consumos = {k: (int(re.search(p, texto_completo, re.IGNORECASE | re.DOTALL).group(1)) if re.search(p, texto_completo, re.IGNORECASE | re.DOTALL) else 0) for k, p in patrones_kwh.items()}
    
    match_actual = re.search(r"(?:Total\s+importe|Total\s+factura|Electricidad).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    importe_real = float(match_actual.group(1).replace(',', '.')) if match_actual else 0.0
        
    return {"archivo": archivo_pdf.name, "fecha": fecha, "dias": dias, "potencia": pot, "consumos": consumos, "importe_real": importe_actual}

# --- INTERFAZ ---
st.sidebar.header("1. Configuración")
archivo_db = st.sidebar.file_uploader("Sube tu base de datos (Excel)", type=["xlsx"])

st.header("2. Sube tus facturas")
pdfs = st.file_uploader("Selecciona uno o varios PDFs", type=["pdf"], accept_multiple_files=True)

if archivo_db and pdfs:
    # Leer Excel
    df_raw = pd.read_excel(archivo_db, header=1)
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    resultados_globales = []

    for pdf in pdfs:
        datos = extraer_datos(pdf)
        kwh_exc = abs(datos['consumos']['Excedentes'])
        
        # Fila Real
        resultados_globales.append({
            "Archivo": datos['archivo'], "Fecha": datos['fecha'], "Compañía": "🏠 REAL PDF",
            "Punta": datos['consumos']['Punta'], "Llano": datos['consumos']['Llano'], "Valle": datos['consumos']['Valle'],
            "Exc": kwh_exc, "TOTAL (€)": datos['importe_real']
        })

        # Comparativa con Excel
        for _, fila in df_tarifas.iterrows():
            try:
                p_pot = (float(fila['Pot_P1']) + float(fila['Pot_P2']))
                c_fijo = datos['potencia'] * datos['dias'] * p_pot
                c_var = (datos['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                         datos['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                         datos['consumos']['Valle'] * float(fila['Ene_Valle']))
                total = c_fijo + c_var - (kwh_exc * float(fila['Precio_Exc']))
                
                resultados_globales.append({
                    "Archivo": datos['archivo'], "Fecha": datos['fecha'], "Compañía": fila['Compania'],
                    "Punta": datos['consumos']['Punta'], "Llano": datos['consumos']['Llano'], "Valle": datos['consumos']['Valle'],
                    "Exc": kwh_exc, "TOTAL (€)": round(total, 2)
                })
            except: continue

    df_final = pd.DataFrame(resultados_globales).sort_values(by=["Archivo", "TOTAL (€)"])
    st.write("### Resultados de la comparativa:")
    st.dataframe(df_final, use_container_width=True)

    # Botón descarga
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False)
    st.download_button("📥 Descargar reporte en Excel", data=output.getvalue(), file_name="comparativa_luz.xlsx")
else:
    st.info("Espera de archivos... Sube el Excel en la izquierda y los PDFs aquí.")
