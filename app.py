import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

# Função para converter valores de forma segura
def safe_float(value):
    try:
        return float(value.replace(',', '.')) if value else 0.0
    except (TypeError, ValueError):
        return 0.0

def parse_nfe(xml_file):
    try:
        # Lê o conteúdo e limpa espaços
        xml_data = xml_file.read().strip()
        root = ET.fromstring(xml_data)
        
        # Remove namespaces para busca universal (evita o erro de não encontrar tags)
        for el in root.iter():
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        
        data = []
        
        # 1. Busca Número da Nota
        ide = root.find('.//ide')
        nNF = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else "S/N"
        
        # 2. Busca UF do Destinatário (Melhorado para evitar N/A)
        uf_dest = "N/A"
        ie_dest = "ISENTO"
        
        # Tenta encontrar no bloco 'dest'
        dest = root.find('.//dest')
        if dest is not None:
            # Procura UF dentro de 'enderDest' ou direto no 'dest'
            uf_el = dest.find('.//UF')
            if uf_el is not None:
                uf_dest = uf_el.text
            
            # Busca Inscrição Estadual ou Substituto
            ie = dest.find('IE')
            isuf = dest.find('ISUF')
            if isuf is not None and isuf.text:
                ie_dest = isuf.text
            elif ie is not None and ie.text:
                ie_dest = ie.text

        # 3. Varredura de Itens
        for det in root.findall('.//det'):
            prod = det.find('prod')
            xProd = prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else "Produto s/ Nome"
            
            imposto = det.find('imposto')
            
            row = {
                "NFe": nNF,
                "UF_Destino": uf_dest,
                "IE_Substituto": ie_dest,
                "Produto": xProd,
                "vBCST": 0.0,
                "vICMSST": 0.0,
                "vBCUFDest": 0.0,
                "vICMSUFDest": 0.0,
                "vFCPUFDest": 0.0,
                "vFCPST": 0.0
            }
            
            if imposto is not None:
                # Captura ICMS ST e FCP ST
                tags_st = {'vBCST': 'vBCST', 'vICMSST': 'vICMSST', 'vFCPST': 'vFCPST'}
                for tag_xml, col_name in tags_st.items():
                    el = imposto.find(f'.//{tag_xml}')
                    if el is not None:
                        row[col_name] = safe_float(el.text)
                
                # Captura DIFAL (ICMSUFDest)
                difal = imposto.find('.//ICMSUFDest')
                if difal is not None:
                    tags_difal = {'vBCUFDest': 'vBCUFDest', 'vICMSUFDest': 'vICMSUFDest', 'vFCPUFDest': 'vFCPUFDest'}
                    for tag_xml, col_name in tags_difal.items():
                        el = difal.find(tag_xml)
                        if el is not None:
                            row[col_name] = safe_float(el.text)
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro no XML {xml_file.name}: {e}")
        return pd.DataFrame()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Leitor Fiscal Estável", layout="wide")

st.title("📑 Leitor Fiscal: DIFAL, ST e FECP")
st.markdown("Busca aprimorada de UF e correção de erros de conexão.")

# Widget de upload
uploaded_files = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_dfs = []
    
    # Processa os arquivos
    for f in uploaded_files:
        f.seek(0)
        df_nota = parse_nfe(f)
        if not df_nota.empty:
            all_dfs.append(df_nota)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final["Total_FECP"] = df_final["vFCPST"] + df_final["vFCPUFDest"]

        # 1. Resumo por Estado
        st.subheader("📊 Resumo por Estado (UF) e IE")
        resumo = df_final.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        
        resumo.columns = ['Estado', 'IE Substituto', 'Total ST', 'Total DIFAL', 'Total FECP']
        st.table(resumo.style.format({'Total ST': 'R$ {:.2f}', 'Total DIFAL': 'R$ {:.2f}', 'Total FECP': 'R$ {:.2f}'}))

        # 2. Tabela Detalhada
        with st.expander("Ver Detalhes por Produto"):
            st.dataframe(df_final)

        # 3. Download
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Baixar Planilha para Excel", csv, "relatorio_fiscal.csv", "text/csv")
