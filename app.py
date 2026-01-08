import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

def safe_float(value):
    try:
        return float(value.replace(',', '.')) if value else 0.0
    except (TypeError, ValueError):
        return 0.0

def parse_nfe(xml_file):
    try:
        xml_data = xml_file.read().strip()
        root = ET.fromstring(xml_data)
        
        # Limpeza de Namespaces para busca universal
        for el in root.iter():
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        
        data = []
        ide = root.find('.//ide')
        nNF = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else "S/N"
        
        # Busca robusta da UF e IE
        uf_dest = "N/A"
        ie_dest = "ISENTO"
        dest = root.find('.//dest')
        if dest is not None:
            uf_el = dest.find('.//UF')
            if uf_el is not None:
                uf_dest = uf_el.text
            
            ie = dest.find('IE')
            isuf = dest.find('ISUF')
            if isuf is not None and isuf.text:
                ie_dest = isuf.text
            elif ie is not None and ie.text:
                ie_dest = ie.text

        for det in root.findall('.//det'):
            prod = det.find('prod')
            xProd = prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else "Produto s/ Nome"
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
                # ICMS ST e FCP ST
                vICMSST = imposto.find('.//vICMSST')
                vFCPST = imposto.find('.//vFCPST')
                if vICMSST is not None: row["vICMSST"] = safe_float(vICMSST.text)
                if vFCPST is not None: row["vFCPST"] = safe_float(vFCPST.text)
                
                # DIFAL e FCP Destino
                difal = imposto.find('.//ICMSUFDest')
                if difal is not None:
                    vICMSUFDest = difal.find('vICMSUFDest')
                    vFCPUFDest = difal.find('vFCPUFDest')
                    if vICMSUFDest is not None: row["vICMSUFDest"] = safe_float(vICMSUFDest.text)
                    if vFCPUFDest is not None: row["vFCPUFDest"] = safe_float(vFCPUFDest.text)
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro no XML {xml_file.name}: {e}")
        return pd.DataFrame()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Leitor Fiscal Consolidado", layout="wide")

st.title("📑 Apuração Fiscal: DIFAL, ST e FECP")
st.markdown("Relatórios separados por Estado e Somatórios Totais.")

uploaded_files = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_dfs = []
    for f in uploaded_files:
        f.seek(0)
        df_nota = parse_nfe(f)
        if not df_nota.empty:
            all_dfs.append(df_nota)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        # Calcula o FECP Total por linha (ST + DIFAL)
        df_final["Total_FECP"] = df_final["vFCPST"] + df_final["vFCPUFDest"]

        # --- 1. RESUMO POR ESTADO ---
        st.subheader("📊 1. Resumo por Estado (UF) e IE")
        resumo_uf = df_final.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        
        resumo_uf.columns = ['Estado', 'IE Substituto', 'Soma ICMS ST', 'Soma DIFAL', 'Soma FECP']
        st.table(resumo_uf.style.format({'Soma ICMS ST': 'R$ {:.2f}', 'Soma DIFAL': 'R$ {:.2f}', 'Soma FECP': 'R$ {:.2f}'}))

        # --- 2. SOMA TOTAL GERAL ---
        st.subheader("💰 2. Soma Total de Todos os Arquivos")
        total_st = df_final['vICMSST'].sum()
        total_difal = df_final['vICMSUFDest'].sum()
        total_fecp = df_final['Total_FECP'].sum()
        total_geral = total_st + total_difal + total_fecp

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total ST Geral", f"R$ {total_st:.2f}")
        col2.metric("Total DIFAL Geral", f"R$ {total_difal:.2f}")
        col3.metric("Total FECP Geral", f"R$ {total_fecp:.2f}")
        col4.subheader(f"Geral: R$ {total_geral:.2f}")

        # --- 3. DETALHAMENTO E DOWNLOAD ---
        with st.expander("Ver Detalhes por Produto/Item"):
            st.dataframe(df_final)

        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha Completa (Excel)", csv, "apuracao_total.csv", "text/csv")
