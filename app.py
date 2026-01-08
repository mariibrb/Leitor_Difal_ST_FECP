import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
from io import BytesIO

def safe_float(value):
    try:
        return float(value.replace(',', '.')) if value else 0.0
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
        
        uf_dest = "N/A"
        ie_dest = "ISENTO"
        dest = root.find('.//dest')
        if dest is not None:
            uf_el = dest.find('.//UF')
            if uf_el is not None: uf_dest = uf_el.text
            ie = dest.find('IE')
            isuf = dest.find('ISUF')
            if isuf is not None and isuf.text: ie_dest = isuf.text
            elif ie is not None and ie.text: ie_dest = ie.text

        for det in root.findall('.//det'):
            prod = det.find('prod')
            xProd = prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else "S/Nome"
            imposto = det.find('imposto')
            
            row = {
                "NFe": nNF,
                "UF_Destino": uf_dest,
                "IE_Substituto": ie_dest,
                "Produto": xProd,
                "vICMSST": 0.0,
                "vICMSUFDest": 0.0,
                "vFCPST": 0.0,
                "vFCPUFDest": 0.0
            }
            
            if imposto is not None:
                vICMSST = imposto.find('.//vICMSST')
                vFCPST = imposto.find('.//vFCPST')
                if vICMSST is not None: row["vICMSST"] = safe_float(vICMSST.text)
                if vFCPST is not None: row["vFCPST"] = safe_float(vFCPST.text)
                
                difal = imposto.find('.//ICMSUFDest')
                if difal is not None:
                    vI = difal.find('vICMSUFDest')
                    vF = difal.find('vFCPUFDest')
                    if vI is not None: row["vICMSUFDest"] = safe_float(vI.text)
                    if vF is not None: row["vFCPUFDest"] = safe_float(vF.text)
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro no XML {xml_file.name}: {e}")
        return pd.DataFrame()

# --- INTERFACE ---
st.set_page_config(page_title="Leitor Fiscal Excel", layout="wide")
st.title("📑 Apuração Fiscal com Abas Excel")

uploaded_files = st.file_uploader("Suba seus XMLs", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_dfs = []
    for f in uploaded_files:
        f.seek(0)
        df_nota = parse_nfe(f)
        if not df_nota.empty: all_dfs.append(df_nota)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final["Total_FECP"] = df_final["vFCPST"] + df_final["vFCPUFDest"]

        # 1. Gerar Resumo Agrupado
        resumo_uf = df_final.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        resumo_uf.columns = ['Estado', 'IE Substituto', 'Soma ICMS ST', 'Soma DIFAL', 'Soma FECP']

        # Exibir na tela
        st.subheader("📊 Resumo por Estado")
        st.table(resumo_uf.style.format({'Soma ICMS ST': 'R$ {:.2f}', 'Soma DIFAL': 'R$ {:.2f}', 'Soma FECP': 'R$ {:.2f}'}))

        # 2. Criar Arquivo Excel com múltiplas abas em memória
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            resumo_uf.to_excel(writer, index=False, sheet_name='Resumo_Por_Estado')
            df_final.to_excel(writer, index=False, sheet_name='Detalhado_Geral')
        
        processed_data = output.getvalue()

        st.download_button(
            label="📥 Baixar Planilha Excel com Abas",
            data=processed_data,
            file_name="apuracao_completa.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
