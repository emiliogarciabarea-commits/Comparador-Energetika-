
import streamlit as st
import pdfplumber
import pandas as pd
import re
import io
import os

st.set_page_config(page_title="Comparador Luz Pro", layout="wide")

st.title("⚡ Comparador de Tarifas (Coste Neto)")

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

# --- FUNCIÓN DE EXTRACCIÓN (REFORZADA Y DISTINTIVA) ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            texto_content = pagina.extract_text()
            if texto_content:
                texto_completo += texto_content + "\n"

    # 1. Fecha
    m_fecha = re.search(r"(\d{2}/\d{2}/\d{4})", texto_completo)
    fecha_f = m_fecha.group(1) if m_fecha else "S/D"
    
    # 2. Días (Busca el número antes de la palabra 'días')
    m_dias = re.search(r"(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias_f = int(m_dias.group(1)) if m_dias else 30

    # 3. Potencia (Busca específicamente un número seguido de 'kW')
    # Ejemplo: '3,300 kW' o '4.6 kW'
    m_pot = re.search(r"(\d+[.,]\d+|\d+)\s*kW", texto_completo, re.IGNORECASE)
    pot_f = float(m_pot.group(1).replace(',', '.')) if m_pot else 3.3

    # 4. CONSUMOS (Busca específicamente números seguidos de 'kWh')
    def buscar_consumo(etiqueta, texto):
        # Busca la etiqueta (P1, Punta...) y captura el primer número que termine en kWh
        patron = re.compile(etiqueta + r".*?(\d+[.,]\d+|\d+)\s*kWh", re.IGNORECASE | re.DOTALL)
        match = patron.search(texto)
        if match:
            return float(match.group(1).replace(',', '.'))
        return 0.0

    cons = {
        "Punta": buscar_consumo(r"(?:P1|Punta)", texto_completo),
        "Llano": buscar_consumo(r"(?:P2|Llano)", texto_completo),
        "Valle": buscar_consumo(r"(?:P3|Valle)", texto_completo),
        "Excedentes": buscar_consumo(r"(?:Excedentes|Vertida|P4)", texto_completo)
    }

    # 5. Importe Neto (Potencia + Energía antes de impuestos)
    m_val_pot = re.search(r"(?:potencia contratada|Facturación por potencia).*?(\d+[.,]\d+)", texto_completo, re.IGNORECASE)
    m_val_ene = re.search(r"(?:energía consumida|Facturación por energía).*?(\d+[.,]\d+)", texto_completo, re.IGNORECASE)
    
    eur_pot = float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0
    eur_ene = float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0
    neto_real = round(eur_pot + eur_ene, 2)
        
    return {
        "archivo": archivo_pdf.name, "fecha": fecha_f, "dias": dias_f, 
        "potencia": pot_f, "consumos": cons, "neto_real": neto_real
    }

# --- PROCESAMIENTO ---
pdfs = st.file_uploader("Sube tus facturas PDF", type=["pdf"], accept_multiple_files=True)

if df_raw is not None and pdfs:
    df_tarifas = df_raw.iloc[:, [0, 1, 2, 3, 4, 5, 6]].copy()
    df_tarifas.columns = ['Compania', 'Pot_P1', 'Pot_P2', 'Ene_Punta', 'Ene_Llano', 'Ene_Valle', 'Precio_Exc']
    df_tarifas = df_tarifas.dropna(subset=['Compania'])

    res = []
    for pdf in pdfs:
        d = extraer_datos(pdf)
        
        # Fila Real (Extraída del PDF)
        res.append({
            "Archivo": d['archivo'], "Compañía": "🏠 ACTUAL (NETO PDF)",
            "Potencia": d['potencia'],
            "Punta": d['consumos']['Punta'], "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
            "COSTO NETO (€)": d['neto_real']
        })

        # Simulaciones
        for _, fila in df_tarifas.iterrows():
            try:
                fijo = d['potencia'] * d['dias'] * (float(fila['Pot_P1']) + float(fila['Pot_P2']))
                var = (d['consumos']['Punta'] * float(fila['Ene_Punta']) + 
                       d['consumos']['Llano'] * float(fila['Ene_Llano']) + 
                       d['consumos']['Valle'] * float(fila['Ene_Valle']))
                exc = abs(d['consumos']['Excedentes']) * float(fila['Precio_Exc'])
                total_sim = round(fijo + var - exc, 2)
                
                res.append({
                    "Archivo": d['archivo'], "Compañía": str(fila['Compania']),
                    "Potencia": d['potencia'],
                    "Punta": d['consumos']['Punta'], "Llano": d['consumos']['Llano'], "Valle": d['consumos']['Valle'],
                    "COSTO NETO (€)": total_sim
                })
            except: continue

    df_final = pd.DataFrame(res).sort_values(by=["Archivo", "COSTO NETO (€)"])
    st.dataframe(df_final, use_container_width=True)
