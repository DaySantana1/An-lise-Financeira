import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import load_transacoes
from utils import features_cashflow, classificar_momento

st.set_page_config(page_title="Momento da Empresa", layout="wide")
st.title("Análise Detalhada: Momento da Empresa")

@st.cache_data
def load_page_data():
    trans = load_transacoes()
    
    if trans.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    base = features_cashflow(trans)
    perfil = classificar_momento(base)
    return trans, base, perfil

trans, base, perfil = load_page_data()

if perfil.empty:
    st.error("Não foi possível carregar os dados para esta página.")
else:
    id_selecionado = st.selectbox("Selecione a empresa:", sorted(perfil["id"].unique()))
    
    perfil_id = perfil[perfil["id"] == id_selecionado].iloc[0]
    st.metric("Momento Atual", perfil_id['momento'], f"Margem Média: {perfil_id['margem_med']:.1%}")

    hist_empresa = base[base["id"] == id_selecionado].sort_values("ano_mes")
    fig_evolucao = px.line(hist_empresa, x="ano_mes", y=["receita", "despesa", "fluxo_liq"], title="Evolução Mensal")
    st.plotly_chart(fig_evolucao, use_container_width=True)
    
    c1, c2 = st.columns(2)
    with c1:
        despesas_id = trans[trans["id_pgto"] == id_selecionado]
        mix_despesas = despesas_id.groupby("ds_tran")["vl"].sum().reset_index()
        fig_pie_despesas = px.pie(mix_despesas, names="ds_tran", values="vl", hole=0.4, title="Distribuição de Despesas")
        st.plotly_chart(fig_pie_despesas, use_container_width=True)
    with c2:
        receitas_id = trans[trans["id_rcbe"] == id_selecionado]
        mix_receitas = receitas_id.groupby("ds_tran")["vl"].sum().reset_index()
        fig_pie_receitas = px.pie(mix_receitas, names="ds_tran", values="vl", hole=0.4, title="Distribuição de Receitas")
        st.plotly_chart(fig_pie_receitas, use_container_width=True)
