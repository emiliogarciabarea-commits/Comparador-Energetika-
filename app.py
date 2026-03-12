
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador de Tarifas Eléctricas")
st.markdown("Comparativa basada estrictamente en el **Subtotal** de la factura.")

# --- CONFIGURACIÓN DE LA BASE DE DATOS POR DEFECTO ---
ARCHIVO_DB_POR_DEFECTO = "tarifas_companias.xlsx"

if os.path.exists(ARCHIVO_DB_POR_DEFECTO):
    df_raw = pd.read_excel(ARCHIVO_DB_POR_DEFECTO, header=1)
    st.sidebar.success(f"✅ Base de datos '{ARCHIVO_DB_POR_DEFECTO}' cargada.")
else:
    st.sidebar.warning("⚠️ Sube el Excel de Tarifas en el lateral.")
    archivo_subido = st.sidebar.file_uploader("Sube tu Excel", type=["xlsx"])
    df_raw = pd.read_excel(archivo_subido, header=1) if archivo_subido else None

# --- FUNCIÓN DE EXTRACCIÓN ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_content = pagina.extract_text()
            if texto_content:
                texto_completo += texto_content + "\n"

    # 1. Fecha
    match_fecha = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha_val = match_fecha.group(1) if match_fecha else "S/D"

    # 2. Días
    match_dias = re.search(r"(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias_val = int(match_dias.group(1)) if match_dias else 30

    # 3. Potencia
    match_potencia = re.search(r"(\d+[.,]\d+|\d+)\s*kW(?!h)", texto_completo, re.IGNORECASE)
    pot_val = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 4.6

    # 4. Consumos
    patrones_kwh = {
        "Punta": r"(?:P1|Punta).*?(\d+)\s*kWh",
        "Llano": r"(?:P2|Llano).*?(\d+)\s*kWh",
        "Valle": r"(?:P3|Valle).*?(\d+)\s*kWh",
        "Excedentes": r"(?:Excedentes|Energía\s+vertida).*?(-?\d+)\s*kWh"
    }
    consumos = {k: 0 for k in patrones_kwh}
    for k, p in patrones_kwh.items():
        m = re.search(p, texto_completo, re.IGNORECASE | re.DOTALL)
        if m: consumos[k] = abs(int(m.group(1)))

    # 5. EXTRACCIÓN ESPECÍFICA DEL SUBTOTAL
    # Busca la palabra 'Subtotal', ignora espacios y captura el número antes del €
    # La regex se asegura de buscar el valor numérico pegado al símbolo de euro
    regex_subtotal = r"Subtotal.*?(\d+[.,]\d+)\s*€"
    match_subtotal = re.search(regex_subtotal, texto_completo, re.IGNORECASE)
    
    if match_subtotal:
        importe_actual = float(match_subtotal.group(1).replace(',', '.'))
    else:
        # Si no existe la palabra Subtotal, buscamos el último valor antes del total (que suele ser el subtotal)
        importes = re.findall(r"(\d+[.,]\d+)\s*€", texto_completo)
        importe_actual = float(importes[-2].replace(',', '.')) if len(importes) >= 2 else 0.0
        
    return {
        "archivo": archivo_pdf.name, "fecha": fecha_val, "dias": dias_val, 
        "potencia": pot_val, "consumos": consumos, "importe_real": importe_actual
    }

# --- INTERFAZ ---
st.header("Sube tus facturas PDF")
archivos_pdf = st.file_uploader("Sube tus PDFs", type=["pdf"], accept_multiple_files=True)

if df_raw is not None and archivos_pdf:
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    ranking = []
    for pdf in archivos_pdf:
        try:
            d = extraer_datos(pdf)
            exc_kwh = d['consumos']['Excedentes']
            
            # Factura Actual
            ranking.append({
                "Archivo": d['archivo'], "Compañía": "🏠 ACTUAL (Subtotal)",
                "TOTAL (€)": d['importe_real'], "Días": d['dias']
            })

            # Comparativa
            for _, fila in df_tarifas.iterrows():
                coste_p = d['potencia'] * d['dias'] * (float(fila['Pot_P1']) + float(fila['Pot_P2']))
                coste_e = (d['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                           d['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                           d['consumos']['Valle'] * float(fila['Ene_Valle']))
                total_sim = round(coste_p + coste_e - (exc_kwh * float(fila['Precio_Exc'])), 2)
                
                ranking.append({
                    "Archivo": d['archivo'], "Compañía": str(fila['Compania']),
                    "TOTAL (€)": total_sim, "Días": d['dias']
                })
        except Exception as e:
            st.error(f"Error en {pdf.name}: {e}")

    df_final = pd.DataFrame(ranking).sort_values(by=["Archivo", "TOTAL (€)"])
    st.write("### 📊 Tabla Comparativa")
    st.dataframe(df_final, use_container_width=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_final.to_excel(writer, index=False)
    st.download_button("📥 Descargar Excel", data=buffer.getvalue(), file_name="comparativa_subtotal.xlsx")
