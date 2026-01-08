import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

def parse_nfe(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    data = []
    
    # Dados da Nota e Destinatário
    ide = root.find('.//ns:ide', ns)
    dest = root.find('.//ns:dest', ns)
    
    nNF = ide.find('ns:nNF', ns).text if ide is not None else "N/A"
    uf_dest = dest.find('ns:UF', ns).text if dest is not None else "N/A"
    
    # Tenta pegar a Inscrição de Substituto Tributário (ISUF), se não tiver, pega a IE
    ie_dest = "N/A"
    if dest is not None:
        isuf = dest.find('ns:ISUF', ns)
        ie = dest.find('ns:IE', ns)
        ie_dest = isuf.text if isuf is not None else (ie.text if ie is not None else "Isento/Nulo")

    # Varredura de itens
    for det in root.findall('.//ns:det', ns):
        prod = det.find('ns:prod', ns)
        imposto = det.find('ns:imposto', ns)
        
        row = {
            "NFe": nNF,
            "UF_Destino": uf_dest,
            "IE_Substituto": ie_dest,
            "Produto": prod.find('ns:xProd', ns).text,
            "vBCST": 0.0,
            "vICMSST": 0.0,
            "vBCUFDest": 0.0,
            "vICMSUFDest": 0.0,
            "vFCPUFDest": 0.0,
            "vFCPST": 0.0
        }
        
        # ICMS ST e FCP ST
        icms = imposto.find('.//ns:ICMS', ns)
        if icms is not None:
            for child in icms:
                vBCST = child.find('ns:vBCST', ns)
                vICMSST = child.find('ns:vICMSST', ns)
                vFCPST = child.find('ns:vFCPST', ns)
                if vBCST is not None: row["vBCST"] = float(vBCST.text)
                if vICMSST is not None: row["vICMSST"] = float(vICMSST.text)
                if vFCPST is not None: row["vFCPST"] = float(vFCPST.text)

        # DIFAL e FCP Destino
        icms_uf_dest = imposto.find('.//ns:ICMSUFDest', ns)
        if icms_uf_dest is not None:
            vBCUFDest = icms_uf_dest.find('ns:vBCUFDest', ns)
            vICMSUFDest = icms_uf_dest.find('ns:vICMSUFDest', ns)
            vFCPUFDest = icms_uf_dest.find('ns:vFCPUFDest', ns)
            if vBCUFDest is not None: row["vBCUFDest"] = float(vBCUFDest.text)
            if vICMSUFDest is not None: row["vICMSUFDest"] = float(vICMSUFDest.text)
            if vFCPUFDest is not None: row["vFCPUFDest"] = float(vFCPUFDest.text)
            
        data.append(row)
    return pd.DataFrame(data)

st.set_page_config(page_title="Leitor Fiscal por UF", layout="wide")
st.title("📑 Leitor Fiscal: DIFAL, ST e FECP por Estado")
st.markdown("Extração de dados para apuração de inscrições de Substituto Tributário.")

uploaded_files = st.file_uploader("Arraste seus XMLs aqui", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        try:
            df_nota = parse_nfe(uploaded_file)
            all_data.append(df_nota)
        except Exception as e:
            st.error(f"Erro no arquivo {uploaded_file.name}: {e}")
    
    if all_data:
        df_total = pd.concat(all_data, ignore_index=True)
        
        # Criando a coluna de Total FECP (Soma do ST e do DIFAL)
        df_total['Total_FECP'] = df_total['vFCPST'] + df_total['vFCPUFDest']

        # --- SEÇÃO DE RESUMO POR ESTADO ---
        st.subheader("📊 Resumo Consolidado por UF / IE")
        
        resumo = df_total.groupby(['UF_Destino', 'IE_Substituto']).agg({
            'vICMSST': 'sum',
            'vICMSUFDest': 'sum',
            'Total_FECP': 'sum'
        }).reset_index()
        
        # Renomeando colunas para ficar mais claro no relatório
        resumo.columns = ['Estado', 'Inscrição Estadual', 'Total ICMS ST', 'Total DIFAL', 'Total FECP']
        st.table(resumo)

        # --- SEÇÃO DETALHADA ---
        st.subheader("🔍 Detalhamento por Item")
        st.dataframe(df_total)
        
        # Download
        csv = df_total.to_csv(index=False).encode('utf-8')
        st.download_button(label="Baixar Planilha Completa (CSV)", data=csv, file_name="apuracao_fiscal.csv", mime="text/csv")
