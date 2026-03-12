
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador: Consumo Real vs Lectura Contador")
st.markdown("Extrae el consumo real del periodo (ej. 30,91 kWh) e ignora lecturas (ej. 11.716 kWh).")

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

# --- FUNCIÓN DE EXTRACCIÓN QUIRÚRGICA ---
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

    # B. LÓGICA DE CONSUMO: Captura solo si hay un multiplicador 'x' cerca
    # Esto evita capturar la lectura acumulada del contador (ej. 11.716)
    def buscar_consumo_real(etiquetas, texto):
        for etiqueta in etiquetas:
            # Buscamos: ETIQUETA + ESPACIOS + NUMERO + kWh + ESPACIOS + 'x'
            patron = re.compile(etiqueta + r".*?(\d+[.,]\d+|\d+)\s*kWh\s*x", re.IGNORECASE | re.DOTALL)
            match = patron.search(texto)
            if match:
                return float(match.group(1).replace(',', '.'))
        return 0.0

    consumos = {
        "Punta": buscar_consumo_real([r"P1", r"Consumo electricidad Punta"], texto_completo),
        "Llano": buscar_consumo_real([r"P2", r"Consumo electricidad Llano"], texto_completo),
        "Valle": buscar_consumo_real([r"P3", r"Consumo electricidad Valle"], texto_completo)
    }

    # C. Importe Neto (Potencia + Energía)
    # Energía XXI: 'Por potencia contratada 7,98 €' + 'Por energía consumida 14,96 €'
    m_p = re.search(r"(?:potencia contratada|Facturación por potencia).*?(\d+[.,]\d+)", texto_completo, re.IGNORECASE)
    m_e = re.search(r"(?:energía consumida|Facturación por energía).*?(\d+[.,]\d+)", texto_completo, re.IGNORECASE)
    
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
            # Fila Real (Debería dar Neto: 22,94€ en tu factura)
            res.append({
                "Archivo": d['archivo'], "Compañía": "🏠 ACTUAL (NETO PDF)",
                "Pot": d['potencia'], "Punta": d['consumos']['Punta'], 
                "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
                "COSTO NETO (€)": d['neto_real']
            })
            # Simulaciones
            for _, fila in df_tarifas.iterrows():
                fijo = d['potencia'] * d['dias'] * (float(fila['Pot_P1']) + float(fila['Pot_P2']))
                var = (d['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                       d['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                       d['consumos']['Valle'] * float(fila['Ene_Valle']))
                res.append({
                    "Archivo": d['archivo'], "Compañía": str(fila['Compania']),
                    "Pot": d['potencia'], "Punta": d['consumos']['Punta'], 
                    "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
                    "COSTO NETO (€)": round(fijo + var, 2)
                })
        except Exception as e: st.error(f"Error: {e}")

    st.dataframe(pd.DataFrame(res), use_container_width=True)
