import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

def get_text(element, ns):
    """Função auxiliar para evitar erro de 'NoneType'"""
    if element is not None:
        return element.text
    return "0.00"

def parse_nfe(xml_file):
    try:
        # Lê o conteúdo do arquivo
        content = xml_file.read()
        root = ET.fromstring(content)
        
        # Define o namespace padrão da NF-e
        ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
        
        data = []
        
        # Localiza Identificação e Destinatário com tratamento de erro
        ide = root.find('.//ns:ide', ns)
        dest = root.find('.//ns:dest', ns)
        
        nNF = ide.find('ns:nNF', ns).text if ide is not None and ide.find('ns:nNF', ns) is not None else "S/N"
        
        # Dados do Destinatário
        uf_dest = "N/A"
        ie_dest = "N/A"
        
        if dest is not None:
            uf_el = dest.find('ns:UF', ns)
            uf_dest = uf_el.text if uf_el is not None else "N/A"
            
            isuf = dest.find('ns:ISUF', ns)
            ie = dest.find('ns:IE', ns)
            if isuf is not None:
                ie_dest = isuf.text
            elif ie is not None:
                ie_dest = ie.text
            else:
                ie_dest = "ISENTO"

        # Varredura de itens
        for det in root.findall('.//ns:det', ns):
            prod = det.find('ns:prod', ns)
            xProd = prod.find('ns:xProd', ns).text if prod is not None else "Produto s/ nome"
            
            imposto = det.find('ns:imposto', ns)
            
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
                # Procura valores de ST e FCP ST
                for st_tag in ['.//ns:vBCST', './/ns:vICMSST', './/ns:vFCPST']:
                    el = imposto.find(st_tag, ns)
                    if el is not None:
                        field_name = st_tag.split(':')[-1]
                        row[field_name] = float(el.text) if el.text else 0.0
                
                # Procura valores de DIFAL (ICMSUFDest)
                difal = imposto.find('.//ns:ICMSUFDest', ns)
                if difal is not None:
                    vBCUFDest = difal.find('ns:vBCUFDest', ns)
                    vICMSUFDest = difal.find('ns:vICMSUFDest', ns)
                    vFCPUFDest = difal.find('ns:vFCPUFDest', ns)
                    
                    row["vBCUFDest"] = float(vBCUFDest.text) if vBCUFDest is not None else 0.0
                    row["vICMSUFDest"] = float(vICMSUFDest.text) if vICMSUFDest is not None else 0.0
                    row["vFCPUFDest"] = float(vFCPUFDest.text) if vFCPUFDest is not None else 0.0
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao processar o arquivo: {e}")
        return pd.DataFrame()

# Interface do App
st.set_page_config(page_title="Leitor Fiscal", layout="wide")
st.title("📑 Leitor Fiscal: DIFAL, ST e FECP")

files = st.file_uploader("Suba seus XMLs aqui", type="xml", accept_multiple_files=True)

if files:
    all_dfs = []
    for f in files:
        df = parse_nfe(f)
        if not df.empty:
            all_dfs.append(df)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        df_final["Total_FECP"] = df_final["vFCPST"] + df_final["vFCPUFDest"]

        st.subheader("📊 Resumo Consolidado por UF")
        resumo = df_final.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        
        resumo.columns = ['Estado', 'IE Substituto', 'Total ST', 'Total DIFAL', 'Total FECP']
        st.table(resumo.style.format({'Total ST': 'R$ {:.2f}', 'Total DIFAL': 'R$ {:.2f}', 'Total FECP': 'R$ {:.2f}'}))

        st.subheader("🔍 Dados Detalhados")
        st.dataframe(df_final)

        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button("Baixar Planilha Excel (CSV)", csv, "apuracao.csv", "text/csv")
