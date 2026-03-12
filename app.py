
import streamlit as st
import pdfplumber
import pandas as pd
import re
import os

st.set_page_config(page_title="Comparador Luz Multiformato", layout="wide")

st.title("⚡ Comparador de Facturas (Energía XXI / Naturgy)")
st.markdown("Extrae consumos de Mercado Regulado y Mercado Libre.")

# --- FUNCIÓN DE EXTRACCIÓN ROBUSTA ---
def extraer_datos(archivo_pdf):
    texto_completo = ""
    with pdfplumber.open(archivo_pdf) as pdf:
        for pagina in pdf.pages:
            content = pagina.extract_text()
            if content: texto_completo += content + "\n"

    # A. Días y Potencia
    m_dias = re.search(r"(\d+)\s*días", texto_completo, re.IGNORECASE)
    dias = int(m_dias.group(1)) if m_dias else 30
    
    # Busca potencia (captura el primer valor tipo 3,3 o 4,4 seguido de kW)
    m_pot = re.search(r"(\d+[.,]\d+|\d+)\s*kW(?!h)", texto_completo, re.IGNORECASE)
    potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 3.3

    # B. LÓGICA DE CONSUMO (Adaptada a ambos formatos)
    def buscar_consumo(patrones, texto):
        for p in patrones:
            # Esta regex busca el número antes de 'kWh' que esté seguido de un multiplicador ('x', 'a' o un precio)
            # Ejemplo Energía XXI: "30,910 kWh x" o "30,910 kWh a"
            # Ejemplo Naturgy: "x 0,203 €/kWh 
 60 kWh" (Busca el número que está cerca de la etiqueta)
            regex = p + r".*?(\d+[.,]\d+|\d+)\s*kWh"
            match = re.search(regex, texto, re.IGNORECASE | re.DOTALL)
            if match:
                val = float(match.group(1).replace(',', '.'))
                # Filtro de seguridad: si el valor es > 1000, probablemente es una lectura del contador, no el consumo
                if val < 1000: return val
        return 0.0

    consumos = {
        "Punta": buscar_consumo([r"P1", r"Consumo electricidad Punta", r"Punta"], texto_completo),
        "Llano": buscar_consumo([r"P2", r"Consumo electricidad Llano", r"Llano"], texto_completo),
        "Valle": buscar_consumo([r"P3", r"Consumo electricidad Valle", r"Valle"], texto_completo)
    }

    # C. Importe Neto (Suma de Término Fijo + Variable)
    m_p = re.search(r"(?:potencia contratada|Facturación por potencia|Término potencia).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    m_e = re.search(r"(?:energía consumida|Facturación por energía|Consumo electricidad).*?(\d+[.,]\d+)\s*€", texto_completo, re.IGNORECASE)
    
    val_p = float(m_p.group(1).replace(',', '.')) if m_p else 0.0
    val_e = float(m_e.group(1).replace(',', '.')) if m_e else 0.0
    neto_real = round(val_p + val_e, 2)
        
    return {
        "archivo": archivo_pdf.name, "dias": dias, "potencia": potencia, 
        "consumos": consumos, "neto_real": neto_real
    }

# --- INTERFAZ ---
pdfs = st.file_uploader("Sube tus facturas (Energía XXI o Naturgy)", type=["pdf"], accept_multiple_files=True)

if pdfs:
    res = []
    for pdf in pdfs:
        try:
            d = extraer_datos(pdf)
            res.append({
                "Archivo": d['archivo'], 
                "Días": d['dias'],
                "Pot": d['potencia'], 
                "Punta (kWh)": d['consumos']['Punta'], 
                "Llano (kWh)": d['consumos']['Llano'], 
                "Valle (kWh)": d['consumos']['Valle'],
                "Neto Real (€)": d['neto_real']
            })
        except Exception as e: st.error(f"Error en {pdf.name}: {e}")

    if res:
        st.write("### Datos Extraídos")
        st.dataframe(pd.DataFrame(res), use_container_width=True)
