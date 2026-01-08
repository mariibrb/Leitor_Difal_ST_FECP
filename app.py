import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

def safe_float(value):
    try:
        if isinstance(value, str):
            return float(value.replace(',', '.'))
        return float(value) if value is not None else 0.0
    except (TypeError, ValueError):
        return 0.0

def parse_nfe(xml_file):
    try:
        xml_data = xml_file.read().strip()
        root = ET.fromstring(xml_data)
        for el in root.iter():
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        
        data = []
        ide = root.find('.//ide')
        nNF = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else "S/N"
        
        dest = root.find('.//dest')
        uf_dest = "N/A"
        ie_dest = "ISENTO"
        if dest is not None:
            uf_el = dest.find('.//UF')
            if uf_el is not None: uf_dest = uf_el.text
            ie = dest.find('IE')
            isuf = dest.find('ISUF')
            if isuf is not None and isuf.text: ie_dest = isuf.text
            elif ie is not None and ie.text: ie_dest = ie.text

        for det in root.findall('.//det'):
            imposto = det.find('imposto')
            row = {
                "NFe": nNF, "Estado": uf_dest, "IE": ie_dest,
                "ST": 0.0, "DIFAL": 0.0, "FCP": 0.0, "FCP_ST": 0.0
            }
            
            if imposto is not None:
                vST = imposto.find('.//vICMSST')
                vFST = imposto.find('.//vFCPST')
                if vST is not None: row["ST"] = safe_float(vST.text)
                if vFST is not None: row["FCP_ST"] = safe_float(vFST.text)
                
                difal = imposto.find('.//ICMSUFDest')
                if difal is not None:
                    vD = difal.find('vICMSUFDest')
                    vF = difal.find('vFCPUFDest')
                    if vD is not None: row["DIFAL"] = safe_float(vD.text)
                    if vF is not None: row["FCP"] = safe_float(vF.text)
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro no XML {xml_file.name}: {e}")
        return pd.DataFrame()

# --- INTERFACE ---
st.set_page_config(page_title="Leitor Fiscal", layout="wide")
st.title("📑 Relatório ST, DIFAL e FCP")

files = st.file_uploader("Arraste seus XMLs", type="xml", accept_multiple_files=True)

if files:
    all_dfs = []
    for f in files:
        f.seek(0)
        df_nota = parse_nfe(f)
        if not df_nota.empty: all_dfs.append(df_nota)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        
        # Agrupamento por Estado
        resumo = df_final.groupby('Estado').agg({
            'ST': 'sum', 'DIFAL': 'sum', 'FCP': 'sum', 'FCP_ST': 'sum'
        }).reset_index()

        # Lista completa de estados para o layout
        lista_estados = ["AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT","PA",
                         "PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"]
        
        resumo_full = pd.DataFrame(lista_estados, columns=['Estado'])
        resumo_full = resumo_full.merge(resumo, on='Estado', how='left').fillna(0)

        # Divisão para o layout lado a lado
        parte1 = resumo_full.iloc[:14].reset_index(drop=True)
        parte2 = resumo_full.iloc[14:].reset_index(drop=True)
        
        # Renomeia colunas da parte 2 para evitar o erro de duplicidade
        parte2.columns = [f"{col} " for col in parte2.columns]
        
        resumo_visual = pd.concat([parte1, parte2], axis=1)

        st.subheader("📊 Resumo por Estado")
        st.dataframe(resumo_visual.style.format(precision=2))

        # Totais Gerais
        st.subheader("💰 Totais Consolidados")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total ST", f"R$ {df_final['ST'].sum():,.2f}")
        c2.metric("Total DIFAL", f"R$ {df_final['DIFAL'].sum():,.2f}")
        c3.metric("Total FCP", f"R$ {df_final['FCP'].sum():,.2f}")
        c4.metric("Total FCP-ST", f"R$ {df_final['FCP_ST'].sum():,.2f}")

        # Excel
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            resumo_visual.to_excel(writer, index=False, sheet_name='Resumo_Estados')
            df_final.to_excel(writer, index=False, sheet_name='Dados_Detalhados')
        
        st.download_button(
            label="📥 Baixar Planilha Excel (.xlsx)",
            data=output.getvalue(),
            file_name="relatorio_fiscal.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
