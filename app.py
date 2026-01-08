import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd
import io

def safe_float(value):
    """Converte texto para número de forma segura."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def parse_nfe(xml_file):
    try:
        # Lê o conteúdo e remove possíveis espaços em branco extras
        xml_data = xml_file.read()
        # O strip() ajuda a evitar erros de parsing no início do arquivo
        root = ET.fromstring(xml_data.strip())
        
        # Remove namespaces para busca universal (isso resolve 99% dos erros de NoneType)
        for el in root.iter():
            if '}' in el.tag:
                el.tag = el.tag.split('}', 1)[1]
        
        data = []
        
        # Identificação Básica
        ide = root.find('.//ide')
        nNF = ide.find('nNF').text if ide is not None and ide.find('nNF') is not None else "S/N"
        
        # Dados do Destinatário (UF e IE)
        dest = root.find('.//dest')
        uf_dest = "N/A"
        ie_dest = "ISENTO"
        
        if dest is not None:
            uf_el = dest.find('UF')
            uf_dest = uf_el.text if uf_el is not None else "N/A"
            
            # Busca IE ou Inscrição de Substituto
            ie = dest.find('IE')
            isuf = dest.find('ISUF')
            if isuf is not None and isuf.text:
                ie_dest = isuf.text
            elif ie is not None and ie.text:
                ie_dest = ie.text

        # Varredura de Itens (det)
        for det in root.findall('.//det'):
            prod = det.find('prod')
            xProd = prod.find('xProd').text if prod is not None and prod.find('xProd') is not None else "Produto não identificado"
            
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
                # Busca valores de ST e FCP ST em qualquer lugar dentro de 'imposto'
                vBCST = imposto.find('.//vBCST')
                vICMSST = imposto.find('.//vICMSST')
                vFCPST = imposto.find('.//vFCPST')
                
                if vBCST is not None: row["vBCST"] = safe_float(vBCST.text)
                if vICMSST is not None: row["vICMSST"] = safe_float(vICMSST.text)
                if vFCPST is not None: row["vFCPST"] = safe_float(vFCPST.text)
                
                # Busca valores de DIFAL (ICMSUFDest)
                difal = imposto.find('.//ICMSUFDest')
                if difal is not None:
                    vBCUFDest = difal.find('vBCUFDest')
                    vICMSUFDest = difal.find('vICMSUFDest')
                    vFCPUFDest = difal.find('vFCPUFDest')
                    
                    if vBCUFDest is not None: row["vBCUFDest"] = safe_float(vBCUFDest.text)
                    if vICMSUFDest is not None: row["vICMSUFDest"] = safe_float(vICMSUFDest.text)
                    if vFCPUFDest is not None: row["vFCPUFDest"] = safe_float(vFCPUFDest.text)
            
            data.append(row)
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro crítico no arquivo {xml_file.name}: {e}")
        return pd.DataFrame()

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title="Leitor Fiscal Master", layout="wide")

st.title("📑 Leitor Fiscal: DIFAL, ST e FECP")
st.markdown("Esta versão ignora erros de estrutura e foca na captura dos valores de impostos.")

uploaded_files = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_dfs = []
    
    for f in uploaded_files:
        # Reset do ponteiro do arquivo para garantir leitura correta
        f.seek(0)
        df_nota = parse_nfe(f)
        if not df_nota.empty:
            all_dfs.append(df_nota)
    
    if all_dfs:
        df_final = pd.concat(all_dfs, ignore_index=True)
        
        # Cálculo do FECP Total (ST + DIFAL)
        df_final["Total_FECP"] = df_final["vFCPST"] + df_final["vFCPUFDest"]

        # --- EXIBIÇÃO DO RESUMO ---
        st.subheader("📊 Resumo Consolidado por Estado e IE")
        
        resumo = df_final.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        
        # Formatação para visualização
        resumo_formatado = resumo.copy()
        resumo_formatado.columns = ['Estado', 'IE Substituto', 'Total ST', 'Total DIFAL', 'Total FECP']
        
        st.table(resumo_formatado.style.format({
            'Total ST': 'R$ {:.2f}', 
            'Total DIFAL': 'R$ {:.2f}', 
            'Total FECP': 'R$ {:.2f}'
        }))

        # --- EXIBIÇÃO DETALHADA ---
        with st.expander("Clique aqui para ver os dados detalhados por item"):
            st.dataframe(df_final)

        # Botão de Download
        csv = df_final.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Baixar Relatório Completo para Excel",
            data=csv,
            file_name="apuracao_impostos.csv",
            mime="text/csv"
        )
    else:
        st.warning("Nenhum dado válido foi extraído dos arquivos enviados.")
