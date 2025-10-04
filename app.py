import streamlit as st
from data_loader import load_empresas, load_transacoes, resumo_universo

st.set_page_config(page_title="Dashboard de Empresas", layout="wide")
st.title("Dashboard de Empresas")

try:
    # Carrega dados
    empresas = load_empresas()  # data/empresas.csv por padrão
    transacoes = load_transacoes()  # data/transacoes.csv por padrão

    # Calcula resumo
    resumo = resumo_universo(empresas, transacoes)

    # Mostra resumo
    st.subheader("Resumo do Universo de Empresas")
    st.write(resumo)

    # Exibe tabelas completas (opcional)
    with st.expander("Ver Empresas"):
        st.dataframe(empresas)
    with st.expander("Ver Transações"):
        st.dataframe(transacoes)

except FileNotFoundError as e:
    st.error(e)
