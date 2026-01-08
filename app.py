import streamlit as st
import xml.etree.ElementTree as ET
import pandas as pd

def parse_nfe(xml_file):
    tree = ET.parse(xml_file)
    root = tree.getroot()
    ns = {'ns': 'http://www.portalfiscal.inf.br/nfe'}
    data = []
    
    ide = root.find('.//ns:ide', ns)
    nNF = ide.find('ns:nNF', ns).text if ide is not None else "N/A"
    
    for det in root.findall('.//ns:det', ns):
        prod = det.find('ns:prod', ns)
        imposto = det.find('ns:imposto', ns)
        
        row = {
            "Item": det.attrib.get('nItem'),
            "Produto": prod.find('ns:xProd', ns).text,
            "NFe": nNF,
            "vBCST": 0.0,
            "vICMSST": 0.0,
            "vBCUFDest": 0.0,
            "vICMSUFDest": 0.0,
            "vFCPUFDest": 0.0,
            "vFCPST": 0.0
        }
        
        icms = imposto.find('.//ns:ICMS', ns)
        if icms is not None:
            for child in icms:
                vBCST = child.find('ns:vBCST', ns)
                vICMSST = child.find('ns:vICMSST', ns)
                vFCPST = child.find('ns:vFCPST', ns)
                if vBCST is not None: row["vBCST"] = float(vBCST.text)
                if vICMSST is not None: row["vICMSST"] = float(vICMSST.text)
                if vFCPST is not None: row["vFCPST"] = float(vFCPST.text)

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

st.set_page_config(page_title="Leitor XML Fiscal", layout="wide")
st.title("📑 Leitor de DIFAL, ST e FECP")

uploaded_files = st.file_uploader("Escolha os arquivos XML", type="xml", accept_multiple_files=True)

if uploaded_files:
    all_data = []
    for uploaded_file in uploaded_files:
        try:
            df_nota = parse_nfe(uploaded_file)
            all_data.append(df_nota)
        except Exception as e:
            st.error(f"Erro ao ler {uploaded_file.name}: {e}")
    
    if all_data:
        final_df = pd.concat(all_data, ignore_index=True)
        st.subheader("Resumo de Totais")
        c1, c2, c3 = st.columns(3)
        c1.metric("Total ICMS ST", f"R$ {final_df['vICMSST'].sum():.2f}")
        c2.metric("Total DIFAL Destino", f"R$ {final_df['vICMSUFDest'].sum():.2f}")
        c3.metric("Total FECP", f"R$ {(final_df['vFCPST'].sum() + final_df['vFCPUFDest'].sum()):.2f}")

        st.dataframe(final_df)
        csv = final_df.to_csv(index=False).encode('utf-8')
        st.download_button(label="Baixar Dados em CSV", data=csv, file_name="impostos.csv", mime="text/csv")
