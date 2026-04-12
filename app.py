import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.IGNORECASE)

    compania = "Genérica / Desconocida" # Valor por defecto

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
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

    elif es_octopus:
        compania = "Octopus Energy"
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'\((\d+)\s+días\)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_punta = re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_val_pot = re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_val_ene = re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        v_pot = float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0
        v_ene = float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0
        total_real = v_pot + v_ene
        m_exc = re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = float(m_exc.group(1).replace(',', '.')) if m_exc else 0.0

    elif es_total_energies:
        compania = "TotalEnergies"
        m_fecha = re.search(r'Fecha\s+emisión:\s*([\d.]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias_meta = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias_meta.group(1)) if m_dias_meta else 0
        m_pot_meta = re.search(r'Potencia\s+P1:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_meta.group(1).replace(',', '.')) if m_pot_meta else 0.0
        v_consumo_final = 0.0
        v_potencia_final = 0.0

        # 1. Extraer Subtotal de Energía (Consumo)
        # Buscamos el texto entre 'Consumo (real)' y 'Potencia'
        m_bloque_cons = re.search(r'Consumo\s+\(real\)(.*?)Potencia', texto_completo, re.DOTALL | re.IGNORECASE)
        if m_bloque_cons:
            importes_cons = re.findall(r'([\d,.]+)\s*€', m_bloque_cons.group(1))
            if importes_cons:
                # El subtotal es siempre el último valor del bloque de consumo
                v_consumo_final = float(importes_cons[-1].replace(',', '.'))

        # 2. Extraer Subtotal de Potencia
        # Buscamos el texto entre 'Potencia' y 'Otros conceptos'
        m_bloque_pot = re.search(r'Potencia.*?kW(.*?)Otros\s+conceptos', texto_completo, re.DOTALL | re.IGNORECASE)
        if m_bloque_pot:
            importes_pot = re.findall(r'([\d,.]+)\s*€', m_bloque_pot.group(1))
            if importes_pot:
                # El subtotal es siempre el último valor del bloque de potencia
                v_potencia_final = float(importes_pot[-1].replace(',', '.'))

        # Sumamos ambos según tu requerimiento
        total_real = v_consumo_final + v_potencia_final

        # Sumamos ambos según tu requerimiento
        total_real = v_consumo_final + v_potencia_final
        
        # Fallback: Si la suma da 0, intentamos leer el cuadro de "Electricidad" de la página 1
        if total_real == 0:
            m_elec_p1 = re.search(r'Electricidad\s+([\d,.]+)\s*€', texto_completo)
            total_real = float(m_elec_p1.group(1).replace(',', '.')) if m_elec_p1 else 0.0

        def extraer_kwh(tipo, texto):
            patron_consumo = rf'consumos\s+han\s+sido.*?{tipo}[:\s]+([\d,.]+)'
            match_cons = re.search(patron_consumo, texto, re.IGNORECASE | re.DOTALL)
            if match_cons:
                return float(match_cons.group(1).replace('.', '').replace(',', '.'))

            patron_gen = rf'{tipo}.*?([\d,.]+)\s*kWh'
            matches = re.findall(patron_gen, texto, re.IGNORECASE)
            if matches: return float(matches[-1].replace('.', '').replace(',', '.'))
            return 0.0
        
        consumos = {
            'punta': extraer_kwh('Punta', texto_completo),
            'llano': extraer_kwh('Llano', texto_completo),
            'valle': extraer_kwh('Valle', texto_completo)
        }
        
        m_excedentes = re.findall(r'(-?[\d,.]+)\s*kWh\s*\(Excedentes\)', texto_completo, re.IGNORECASE)
        excedente = sum(abs(float(x.replace('.', '').replace(',', '.'))) for x in m_excedentes) if m_excedentes else 0.0

    elif es_naturgy:
        compania = "Naturgy"
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        m_dias = re.search(r'Financiación\s+de\s+Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        m_pot = re.search(r'Potencia\s+contratada\s+P1:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        
        m_punta = re.search(r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        
        m_exc = re.search(r'Valoración\s+excedentes\s*(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0
        
        m_subtotal = re.search(r'Subtotal\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        if m_subtotal:
            total_real = float(m_subtotal.group(1).replace(',', '.'))
        else:
            m_total_elec = re.search(r'Total\s+electricidad\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(m_total_elec.group(1).replace(',', '.')) if m_total_elec else 0.0

    elif es_endesa_luz:
        compania = "Endesa Energía"
        # Fecha de emisión
        m_fecha_etiqueta = re.search(r'Fecha.*?emisi.*?([\d/]{8,10})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else "No encontrada"
        
        # Días de facturación
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        # Potencia contratada
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        
        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                # Quitamos puntos de miles y cambiamos coma por punto decimal
                valor_sucio = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
                try: return float(valor_sucio)
                except: return 0.0
            return 0.0

        val_potencia = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo)
        
        # Aislamiento del bloque de Energía kWh para no leer la tabla de Potencia kW
        bloque_energia_match = re.search(r'Energ[ií]a\s+kWh(.*?)(?:Potencia\s+kW|$)', texto_completo, re.DOTALL | re.IGNORECASE)
        texto_solo_kwh = bloque_energia_match.group(1) if bloque_energia_match else texto_completo
        
        val_energia = limpiar_valor_endesa(r'Energ[ií]a(?:\s+consumida(?:\s+de\s+la\s+red)?)?[\s.]*([\d\s.,]+)€', texto_completo)
        total_real = val_potencia + val_energia

        # --- CORRECCIÓN DE CONSUMOS ---
        # Buscamos la palabra y capturamos el último número de la línea DENTRO DEL BLOQUE de kWh
        m_punta = re.search(r'^Punta.*\s+([\d,.]+)$', texto_solo_kwh, re.MULTILINE | re.IGNORECASE)
        m_llano = re.search(r'^Llano.*\s+([\d,.]+)$', texto_solo_kwh, re.MULTILINE | re.IGNORECASE)
        m_valle = re.search(r'^Valle.*\s+([\d,.]+)$', texto_solo_kwh, re.MULTILINE | re.IGNORECASE)
        
        # Si no encuentra por línea completa, intentamos una versión más flexible dentro del bloque
        if not m_punta:
            m_punta = re.search(r'Punta(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_solo_kwh)
        if not m_llano:
            m_llano = re.search(r'Llano(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_solo_kwh)
        if not m_valle:
            m_valle = re.search(r'Valle(?:\s+[\d,.-]+){4}\s+([\d,.]+)', texto_solo_kwh)

        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }

        # Captura de excedentes (importante para facturas con Solar)
        m_exc = re.search(r'Energia\s+vertida\s+a\s+la\s+red\s+([\d,.]+)\s+kWh', texto_completo, re.IGNORECASE)
        excedente = float(m_exc.group(1).replace(',', '.')) if m_exc else 0.0

    elif es_repsol:
        compania = "Repsol"
        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
    
        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
    
        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
    
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)

    # NUEVA LÓGICA PARA CONSUMOS DESGLOSADOS
    # Buscamos tres números decimales seguidos de kWh en la misma línea (típico de la tabla de Repsol)
        m_desglose = re.search(r'([\d,.]+)\s*kWh\s+([\d,.]+)\s*kWh\s+([\d,.]+)\s*kWh', texto_completo)
    
        if m_desglose:
            consumos = {
                'punta': float(m_desglose.group(1).replace(',', '.')),
                'llano': float(m_desglose.group(2).replace(',', '.')),
                'valle': float(m_desglose.group(3).replace(',', '.'))
            }
        else:
        # Fallback: si no encuentra el desglose, intenta pillar el total de la pág 1 como hacías antes
            m_consumo_gen = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
            consumos = {
                'punta': float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0, 
                'llano': 0.0, 
                'valle': 0.0
            }
        
        excedente = 0.0

    elif es_iberdrola:
        compania = "Iberdrola"
        patron_potencia = r'Potencia\s+punta:\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_dias = r'Potencia\s+facturada.*?(\d+)\s+días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_periodo = r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})'
        match_periodo = re.search(patron_periodo, texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = match_periodo.group(2) if match_periodo else "No encontrada"
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_imp_potencia = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_energia = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_imp_potencia.group(1).replace(',', '.')) if m_imp_potencia else 0.0) + (float(m_imp_energia.group(1).replace(',', '.')) if m_imp_energia else 0.0)
        excedente = 0.0

    else:
        if es_xxi: compania = "Energía XXI"
        
        # --- BÚSQUEDA DE FECHA ULTRA-ROBUSTA ---
        m_fecha = re.search(r'Lectura.*?actual.*?real.*?(\d{1,2}.*?\d{4})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1).strip() if m_fecha else "No encontrada"

        # --- BÚSQUEDA DE TOTAL REAL (SUMA POTENCIA + ENERGIA) ---
        m_p_eur = re.search(r'potencia.*?contratada.*?(\d+[\d,.]*)', texto_completo, re.IGNORECASE)
        m_e_eur = re.search(r'energ[íi]a.*?consumida.*?(\d+[\d,.]*)', texto_completo, re.IGNORECASE)
        
        if m_p_eur and m_e_eur:
            total_real = float(m_p_eur.group(1).replace(',', '.')) + float(m_e_eur.group(1).replace(',', '.'))
        else:
            m_alt = re.search(r'Facturaci[oó]n.*?potencia.*?contratada.*?(\d+[\d,.]*)', texto_completo, re.IGNORECASE)
            total_real = float(m_alt.group(1).replace(',', '.')) if m_alt else 0.0

        # --- RESTO DE DATOS ---
        m_pot_kw = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot_kw.group(1).replace(',', '.')) if m_pot_kw else 0.0
        
        patrones_consumo = {
            'punta': [r'P1:?\s*([\d,.]+)\s*kWh', r'Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'P2:?\s*([\d,.]+)\s*kWh', r'Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'P3:?\s*([\d,.]+)\s*kWh', r'Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break

        m_dias = re.search(r'(\d+)\s*días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        m_exc = re.search(r'Valoración\s+excedentes.*?(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE | re.DOTALL)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }


# --- Código Streamlit ---
st.set_page_config(page_title="Comparador Energético", layout="wide")

# --- BLOQUE DEL LOGO ---
if os.path.exists("Logo_Energetika.png"):
    st.image("Logo_Energetika.png", width=280)

st.markdown("### ⚡ Comparador Energetika de Facturas Eléctricas")

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
            cols = ["Compañía", "Fecha", "Días", "Potencia (kW)", "Consumo Punta (kWh)", "Consumo Llano (kWh)", "Consumo Valle (kWh)", "Excedente (kWh)", "Total Real", "Archivo"]
            df_resumen_pdfs = df_resumen_pdfs[cols]

            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                # Se añade column_order para mantener las columnas fijas
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True, column_order=cols)
            if (df_resumen_pdfs["Potencia (kW)"] == 0).any() or (df_resumen_pdfs["Total Real"] == 0).any() or (df_resumen_pdfs["Días"] == 0).any():
                st.warning("⚠️⚠️⚠️ Se han detectado valores nulos en la Potencia, en el Total Real y/o en el número de días de tu factura. Por favor, corrige manualmente los datos de tu factura en la tabla anterior para obtener un cálculo preciso. ⚠️⚠️⚠️")
            
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []
            
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": f"📍 TU FACTURA ACTUAL",
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
            
            df_solo_ofertas = df_comp[~df_comp["Compañía/Tarifa"].str.contains("📍 TU FACTURA")]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa").agg({'Ahorro': 'sum', 'Dias_Factura': 'sum'}).reset_index()
            ranking_total = ranking_total.sort_values(by="Ahorro", ascending=False)

            st.divider()
            
            if not ranking_total.empty:
                st.subheader("🏆 TOP 3 - Mejores Opciones de Ahorro")
                
                st.markdown("""
                    <style>
                    .whatsapp-button {
                        display: inline-block;
                        width: 100%;
                        padding: 12px;
                        text-align: center;
                        text-decoration: none;
                        font-size: 16px;
                        font-weight: bold;
                        border-radius: 8px;
                        margin-top: 10px;
                        border: none;
                    }
                    .whatsapp-button:hover {
                        filter: brightness(90%);
                    }
                    </style>
                """, unsafe_allow_html=True)

                top_3 = ranking_total.head(3)
                cols_top = st.columns(len(top_3))

                # Definimos los colores para el TOP 3
                colores_top = ["#25D366", "#FFD700", "#FF8C00"] # Verde, Amarillo, Naranja
                
                for i, (idx, row) in enumerate(top_3.iterrows()):
                    nombre_cia = row['Compañía/Tarifa']
                    ahorro_total = round(row['Ahorro'], 2)
                    dias_totales = int(row['Dias_Factura']) if row['Dias_Factura'] > 0 else 30
                    
                    ahorro_anual = round((ahorro_total / dias_totales) * 365 * 1.21, 2)
                    color_metrica = "inverse" if ahorro_total < 0 else "normal"

                    if ahorro_total < 0:
                        color_fondo = "#FF4B4B"  # Rojo (Streamlit Red)
                        texto_boton = "PLAN NO RECOMENDADO" # Opcional: cambiar el texto si es negativo
                        color_metrica = "inverse"
                    else:
                        # Asignamos color según posición (0, 1, 2 -> Verde, Amarillo, Naranja)
                        color_fondo = colores_top[i]
                        texto_boton = "CAMBIARME A ESTA COMPAÑÍA"
                        color_metrica = "normal"
                    
                    with cols_top[i]:
                        st.metric(
                            label=f"Ahorro en {dias_totales} días", 
                            value=f"{ahorro_total} €", 
                            delta=f"Opción {i+1}",
                            delta_color=color_metrica
                        )
                        st.metric(
                            label="Estimación Ahorro Anual (IVA inc.)", 
                            value=f"{ahorro_anual} €",
                            delta_color=color_metrica
                        )
                        st.write(f"**Compañía:** {nombre_cia}")
                        
                        msg = f"Hola! He usado el comparador de Energetika y he visto que puedo ahorrar {ahorro_total}€ en {dias_totales} días (aprox. {ahorro_anual}€ al año) con la compañía {nombre_cia}. Me gustaría cambiarme."
                        url_whatsapp = f"https://wa.me/34614676150?text={msg.replace(' ', '%20')}"

                        st.markdown(f'''<a href="{url_whatsapp}" target="_blank" style="text-decoration: none;">
                        <div style="background-color: {color_fondo}; 
                        color: #000000 !important; 
                        padding: 12px; 
                        text-align: center; 
                        border-radius: 8px; 
                        font-weight: bold; 
                        border: none;">
                        {texto_boton}
                        </div>
                        </a>
                        ''', unsafe_allow_html=True)

                        st.markdown(f'''<a href="{url_whatsapp}" target="_blank" class="whatsapp-button" style="background-color: {color_fondo} !important; color: #000000 !important; 
                        text-decoration: none !important; display: block !important; padding: 12px !important; text-align: center !important; border-radius: 8px !important; font-weight: bold !important;
                        cursor: pointer !important;">
                        {texto_boton}</a>
                        ''', unsafe_allow_html=True)


            st.divider()
            st.subheader("📊 Comparativa Detallada por Factura")
            
            df_mostrar = df_comp.drop(columns=['Dias_Factura'], errors='ignore')
            
            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Coste (€)": st.column_config.NumberColumn(format="%.2f"),
                    "Ahorro": st.column_config.NumberColumn(
                        format="%.2f",
                        help="Ahorro respecto a tu factura actual"
                    ),
                }
            )
