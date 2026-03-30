
import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    paginas_texto = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            contenido = pagina.extract_text() + "\n"
            texto_completo += contenido
            paginas_texto.append(contenido)

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)

    if es_el_corte_ingles:
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }
        patron_potencia = r'Potencia\s+contratada\s+kW\s+([\d,.]+)'
        match_potencia = re.search(patron_potencia, texto_completo)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
        match_fecha = re.search(patron_fecha, texto_completo)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_total = r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
        excedente = 0.0 

    elif es_naturgy:
        # Fecha de emisión
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        # REFINAMIENTO DE DÍAS: Búsqueda quirúrgica en Bloque 3 de Página 2
        dias = 0
        if len(paginas_texto) >= 2:
            texto_p2 = paginas_texto[1]
            # Extraer solo la sección de detalle para evitar ruido
            inicio_bloque = re.search(r'3\.\s*Detalle', texto_p2, re.IGNORECASE)
            if inicio_bloque:
                seccion_detalle = texto_p2[inicio_bloque.start():]
                # Buscar la línea del término de potencia o energía que siempre lleva los días
                lineas = seccion_detalle.split('\n')
                for linea in lineas:
                    if "días" in linea.lower():
                        # Captura el número que va antes de la palabra "días"
                        m_d = re.search(r'(\d+)\s*días', linea, re.IGNORECASE)
                        if m_d:
                            dias = int(m_d.group(1))
                            break

        # Si el método quirúrgico falla, usamos el cálculo por fechas del periodo
        if dias == 0:
            m_per = re.search(r'del\s+([\d/]{10})\s+al\s+([\d/]{10})', texto_completo, re.IGNORECASE)
            if m_per:
                from datetime import datetime
                try:
                    d1 = datetime.strptime(m_per.group(1), '%d/%m/%Y')
                    d2 = datetime.strptime(m_per.group(2), '%d/%m/%Y')
                    dias = (d2 - d1).days + 1
                except: pass

        # Potencia y Consumos (se mantiene igual)
        m_pot = re.search(r'Potencia\s+contratada\s+P1:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_punta = re.search(r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_exc_kwh = re.findall(r'(-?\d+)\s*kWh.*?Valoración\s+excedentes', texto_completo, re.DOTALL | re.IGNORECASE)
        excedente = abs(float(m_exc_kwh[0])) if m_exc_kwh else 0.0
        m_total = re.search(r'Total\s+a\s+pagar\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

    elif es_total_energies:
        m_fecha = re.search(r'Fecha\s+emisión:\s*([\d.]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias_meta = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias_meta.group(1)) if m_dias_meta else 0
        m_pot_meta = re.search(r'Potencia\s+P1:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_meta.group(1).replace(',', '.')) if m_pot_meta else 0.0
        total_real = 0.0
        lineas = texto_completo.split('\n')
        for linea in lineas:
            linea_limpia = linea.strip()
            if re.search(r'^(\d{2}\.\d{2}\.\d{4})|(\d+\s+día\(s\))', linea_limpia):
                m_valor = re.findall(r'([\d,.]+)\s*€\s*$', linea_limpia)
                if m_valor: total_real += float(m_valor[-1].replace('.', '').replace(',', '.'))
        def extraer_kwh(tipo, texto):
            patron = rf'{tipo}.*?([\d,.]+)\s*kWh'
            matches = re.findall(patron, texto, re.IGNORECASE)
            if matches: return float(matches[-1].replace('.', '').replace(',', '.'))
            return 0.0
        consumos = {
            'punta': extraer_kwh('Punta', texto_completo),
            'llano': extraer_kwh('Llano', texto_completo),
            'valle': extraer_kwh('Valle', texto_completo)
        }
        excedente = 0.0

    elif es_endesa_luz:
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else "No encontrada"
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        total_real = 0.0
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_repsol:
        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        patron_potencia = r'Potencia\s+punta:\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_dias = r'Potencia\s+facturada.*?(\d+)\s+días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        fecha = "No encontrada"
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        total_real = 0.0
        excedente = 0.0

    else:
        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        fecha = "No encontrada"
        match_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        total_real = 0.0
        excedente = 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}' en el repositorio.")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        datos_facturas = []
        for uploaded_file in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))
                res['Archivo'] = uploaded_file.name
                datos_facturas.append(res)
            except Exception as e:
                st.error(f"Error procesando {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'],
                    "Ahorro": 0.0,
                    "Dias_Factura": fact['Días']
                })

                for index, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1 = pd.to_numeric(tarifa.iloc[1], errors='coerce')
                        c_pot2 = pd.to_numeric(tarifa.iloc[2], errors='coerce')
                        d_punta = pd.to_numeric(tarifa.iloc[3], errors='coerce')
                        e_llano = pd.to_numeric(tarifa.iloc[4], errors='coerce')
                        f_valle = pd.to_numeric(tarifa.iloc[5], errors='coerce')
                        g_excedente = pd.to_numeric(tarifa.iloc[6], errors='coerce')

                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + \
                                         (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * d_punta) + \
                                         (fact['Consumo Llano (kWh)'] * e_llano) + \
                                         (fact['Consumo Valle (kWh)'] * f_valle) - \
                                         (fact['Excedente (kWh)'] * g_excedente)
                        
                        ahorro = fact['Total Real'] - coste_estimado
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(ahorro, 2),
                            "Dias_Factura": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            st.subheader("📊 Comparativa Detallada por Factura")
            st.dataframe(df_comp.drop(columns=['Dias_Factura'], errors='ignore'), use_container_width=True, hide_index=True)
