
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

    elif es_repsol:
        # 1. Fecha de emisión
        patron_fecha = r'Fecha\s+de\s+emisión:\s*([\d/]+)'
        match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"

        # 2. Total Real (Suma de Término fijo y Energía)
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_energia = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        val_fijo = float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0
        val_en = float(m_energia.group(1).replace(',', '.')) if m_energia else 0.0
        total_real = val_fijo + val_en

        # 3. Consumos (Punta, Llano, Valle)
        # Buscamos el valor numérico que aparece después de cada palabra de tramo
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)

        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }

        # 4. Potencia y Días para Repsol
        patron_potencia = r'Potencia\s+contratada.*?([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

        patron_dias = r'(\d+)\s*Días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE)
        dias = int(match_dias.group(1)) if match_dias else 0
        excedente = 0.0

    elif es_iberdrola:
        # 1. Potencia (Potencia Punta)
        patron_potencia = r'Potencia\s+punta:\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

        # 2. Días: Número justo antes de "Días" en la fila "Potencia facturada"
        patron_dias = r'Potencia\s+facturada.*?(\d+)\s+días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0

        # 3. Fecha: Busca valores con formato XX/XX/XX y elige el segundo del periodo
        patron_periodo = r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})'
        match_periodo = re.search(patron_periodo, texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = match_periodo.group(2) if match_periodo else "No encontrada"

        # 4. Energía Consumida (Punta, Llano, Valle)
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)

        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }

        # 5. Total Real: "Total importe potencia" + "Total xxx kWh hasta..."
        m_imp_potencia = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_energia = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)

        val_potencia = float(m_imp_potencia.group(1).replace(',', '.')) if m_imp_potencia else 0.0
        val_energia = float(m_imp_energia.group(1).replace(',', '.')) if m_imp_energia else 0.0
        
        total_real = val_potencia + val_energia
        excedente = 0.0

    else:
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
        
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break

        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

        patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
        match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"

        # Lógica especial para Días en Naturgy
        if es_naturgy:
            patron_dias_nat = r'Término\s+potencia\s+P1.*?(\d+)\s+días'
            match_dias_nat = re.search(patron_dias_nat, texto_completo, re.IGNORECASE | re.DOTALL)
            dias = int(match_dias_nat.group(1)) if match_dias_nat else 0
        else:
            patron_dias = r'(\d+)\s*días'
            match_dias = re.search(patron_dias, texto_completo)
            dias = int(match_dias.group(1)) if match_dias else 0

        patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
        match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        
        es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
        if es_xxi:
            m_pot = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            m_ene = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = (float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0) + (float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0)
        else:
            match_total = re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# El resto del código de Streamlit se mantiene igual...
