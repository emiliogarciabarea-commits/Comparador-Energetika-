
import streamlit as st
import pdfplumber
import pandas as pd
import re
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador de Tarifas: Diferenciación Horaria")
st.markdown("Extracción precisa de P1 (Punta), P2 (Llano) y P3 (Valle).")

# --- CARGA DE BASE DE DATOS ---
ARCHIVO_DB_POR_DEFECTO = "tarifas_companias.xlsx"
df_raw = None

if os.path.exists(ARCHIVO_DB_POR_DEFECTO):
    try:
        df_raw = pd.read_excel(ARCHIVO_DB_POR_DEFECTO, header=1)
        st.sidebar.success("✅ Tarifas cargadas.")
    except: pass
else:
    subida = st.sidebar.file_uploader("Sube el Excel de Tarifas", type=["xlsx"])
    if subida: df_raw = pd.read_excel(subida, header=1)

# --- FUNCIÓN DE EXTRACCIÓN POR PERIODOS ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            content = pagina.extract_text()
            if content: texto_completo += content + "\n"

    # A. Datos Generales
    m_dias = re.search(r"(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias = int(m_dias.group(1)) if m_dias else 30
    
    m_pot = re.search(r"(\d+[.,]\d+|\d+)\s*kW(?!h)", texto_completo, re.IGNORECASE)
    potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 3.3

    # B. LÓGICA DE DIFERENCIACIÓN (P1, P2, P3)
    # Buscamos el número que va justo antes de "kWh x" para evitar lecturas totales
    def buscar_periodo(patrones, texto):
        for p in patrones:
            # Captura el valor decimal antes de 'kWh x' o 'kWh a'
            match = re.search(p + r".*?(\d+[.,]\d+)\s*kWh\s*[xa]", texto, re.IGNORECASE | re.DOTALL)
            if match:
                return float(match.group(1).replace(',', '.'))
        return 0.0

    consumos = {
        "Punta": buscar_periodo([r"P1", r"punta"], texto_completo),
        "Llano": buscar_periodo([r"P2", r"llano"], texto_completo),
        "Valle": buscar_periodo([r"P3", r"valle"], texto_completo)
    }

    # C. Importe Neto Real
    m_p = re.search(r"(?:potencia contratada|Facturación por potencia).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    m_e = re.search(r"(?:energía consumida|Facturación por energía).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    
    val_p = float(m_p.group(1).replace(',', '.')) if m_p else 0.0
    val_e = float(m_e.group(1).replace(',', '.')) if m_e else 0.0
    neto_real = round(val_p + val_e, 2)
        
    return {
        "archivo": archivo_pdf.name, "dias": dias, "potencia": potencia, 
        "consumos": consumos, "neto_real": neto_real
    }

# --- INTERFAZ ---
pdfs = st.file_uploader("Sube tus facturas PDF", type=["pdf"], accept_multiple_files=True)

if df_raw is not None and pdfs:
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    res = []
    for pdf in pdfs:
        try:
            d = extraer_datos(pdf)
            # Fila de la Factura Actual
            res.append({
                "Archivo": d['archivo'], "Compañía": "🏠 ACTUAL (NETO PDF)",
                "Pot": d['potencia'], 
                "Punta": d['consumos']['Punta'], 
                "Llano": d['consumos']['Llano'], 
                "Valle": d['consumos']['Valle'],
                "COSTO NETO (€)": d['neto_real']
            })
            
            # Comparativa con otras compañías
            for _, fila in df_tarifas.iterrows():
                fijo = d['potencia'] * d['dias'] * (float(str(fila['Pot_P1']).replace(',','.')) + float(str(fila['Pot_P2']).replace(',','.')))
                var = (d['consumos']['Punta'] * float(str(fila['Ene_Punta']).replace(',','.')) + 
                       d['consumos']['Llano'] * float(str(fila['Ene_Llano']).replace(',','.')) + 
                       d['consumos']['Valle'] * float(str(fila['Ene_Valle']).replace(',','.')))
                res.append({
                    "Archivo": d['archivo'], "Compañía": str(fila['Compania']),
                    "Pot": d['potencia'], 
                    "Punta": d['consumos']['Punta'], 
                    "Llano": d['consumos']['Llano'], 
                    "Valle": d['consumos']['Valle'],
                    "COSTO NETO (€)": round(fijo + var, 2)
                })
        except Exception as e: st.error(f"Error procesando {pdf.name}: {e}")

    st.dataframe(pd.DataFrame(res), use_container_width=True)
