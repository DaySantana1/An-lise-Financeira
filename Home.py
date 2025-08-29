import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import load_empresas, load_transacoes
from utils import features_cashflow, classificar_momento, cluster_receita_despesa

st.set_page_config(page_title="Análise de Perfil das Empresas", layout="wide")

# Carrega o CSS
with open("styles.css") as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

@st.cache_data
def load_data():
    empresas = load_empresas()
    trans = load_transacoes()
    
    if empresas.empty or trans.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # --- CÁLCULO DA IDADE DA EMPRESA ---
    data_referencia = pd.to_datetime('2025-01-31') 
    empresas['idade'] = (data_referencia - empresas['dt_abrt']).dt.days / 365.25
    bins = [0, 2, 5, 10, 100] # Adicionado 100 como limite superior
    labels = ['Startup (<2 anos)', 'Em Crescimento (2-5 anos)', 'Madura (5-10 anos)', 'Estabelecida (>10 anos)']
    empresas['faixa_maturidade'] = pd.cut(empresas['idade'], bins=bins, labels=labels, right=False)

    base = features_cashflow(trans)
    perfil = classificar_momento(base)
    perfil_cluster, _ = cluster_receita_despesa(perfil)
    return empresas, trans, base, perfil, perfil_cluster

empresas, trans, base, perfil, perfil_cluster = load_data()

st.markdown('<div class="big-title">Análise de Perfil das Empresas</div>', unsafe_allow_html=True)

if perfil.empty:
    st.error("Não foi possível carregar os dados. Verifique as mensagens de erro acima e seu arquivo Excel.")
else:
    # KPIs Globais
    col1, col2, col3 = st.columns(3)
    dist = perfil["momento"].value_counts(normalize=True)
    with col1:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Total de empresas analisadas", perfil['id'].nunique())
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Momento predominante", dist.idxmax(), f"{(dist.max() * 100):.1f}% do total")
        st.markdown('</div>', unsafe_allow_html=True)
    with col3:
        saldo_med = empresas.groupby("id")["vl_sldo"].last().mean()
        st.markdown('<div class="kpi-card">', unsafe_allow_html=True)
        st.metric("Saldo médio por empresa", f"R$ {saldo_med:,.0f}".replace(",", "."))
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("---")
    
        # Análises Globais
    st.header("Visão Geral do Universo de Empresas")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Distribuição por Momento")
        pie_df = perfil["momento"].value_counts().reset_index()
        fig_pie = px.pie(pie_df, values="count", names="momento", hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
    with c2:
        st.subheader("Clusters de Receita vs. Despesa")
        fig_scatter = px.scatter(perfil_cluster, x="cx_receita", y="cx_despesa", color="momento", hover_data=["id"])
        st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("---")

    cl1, cl2 = st.columns([1, 1])
    with cl1:
        # ANÁLISE POR MATURIDADE DA EMPRESA ---
        st.header("Análise por Maturidade da Empresa")
        maturidade_mapping = empresas[['id', 'faixa_maturidade']].drop_duplicates(subset='id')
        perfil_com_maturidade = pd.merge(perfil, maturidade_mapping, on='id', how='left')
        analise_maturidade = perfil_com_maturidade.groupby('faixa_maturidade', observed=True).agg(
            receita_media=('cx_receita', 'mean'),
            numero_empresas=('id', 'count')
        ).reset_index()
        fig_maturidade = px.bar(
            analise_maturidade,
            x='faixa_maturidade', y='receita_media',
            title='Receita Média por Nível de Maturidade da Empresa',
            labels={'receita_media': 'Receita Média (R$)', 'faixa_maturidade': 'Nível de Maturidade'},
            text='receita_media', color='faixa_maturidade'
        )
        fig_maturidade.update_traces(texttemplate='R$ %{text:,.0f}', textposition='inside')
        fig_maturidade.update_layout(
        legend_title_text='Nível de Maturidade', # Título da legenda
        legend=dict(
        orientation="h",      # Orientação horizontal
        yanchor="bottom",
        y=-0.3,               # Posição vertical (abaixo do gráfico)
        xanchor="center",
        x=0.5                 # Posição horizontal (centralizado)
            )
        )
        st.plotly_chart(fig_maturidade, use_container_width=True)
      
    with cl2:
        # ANÁLISE POR TIPO DE TRANSAÇÃO ---
        st.header("Análise por Tipo de Transação")
        analise_transacoes = trans.groupby('ds_tran').agg(
            valor_total=('vl', 'sum')
        ).reset_index().sort_values('valor_total', ascending=False)
        fig_transacoes = px.pie(
            analise_transacoes.head(10),
            names='ds_tran', values='valor_total',
            title='Distribuição do Valor Total por Tipo de Transação (Top 10)',
            hole=0.4
        )
        st.plotly_chart(fig_transacoes, use_container_width=True)
        fig_transacoes.update_layout(
        legend_title_text='Nível de Maturidade', # Título da legenda
        legend=dict(
        orientation="h",      # Orientação horizontal
        yanchor="bottom",
        y=-0.3,               # Posição vertical (abaixo do gráfico)
        xanchor="center",
        x=0.5                 # Posição horizontal (centralizado)
            )
        )
    st.markdown("---")
    

        # --- SEÇÃO: ANÁLISE POR CNAE ---
    st.header("Análise de Desempenho por Setor (CNAE)")
    cnae_mapping = empresas[['id', 'ds_cnae']].drop_duplicates(subset='id')
    perfil_com_cnae = pd.merge(perfil, cnae_mapping, on='id', how='left')
    analise_cnae = perfil_com_cnae.groupby('ds_cnae').agg(
        receita_total=('cx_receita', 'sum'),
        despesa_total=('cx_despesa', 'sum'),
        numero_empresas=('id', 'count')
    ).reset_index()
    top_cnae = analise_cnae.sort_values('receita_total', ascending=False).head(15)
    fig_cnae = px.bar(
        top_cnae.sort_values('receita_total', ascending=True),
        x='receita_total', y='ds_cnae', orientation='h',
        title='Top 15 Setores por Receita Total',
        labels={'receita_total': 'Receita Total (R$)', 'ds_cnae': 'Setor (CNAE)'},
        text='receita_total'
    )
    fig_cnae.update_traces(texttemplate='R$ %{text:,.2s}', textposition='outside')
    fig_cnae.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', yaxis={'categoryorder':'total ascending'})
    st.plotly_chart(fig_cnae, use_container_width=True)

    # # Análise Individual
    # st.header("Análise Detalhada por Empresa")
    # id_selecionado = st.selectbox("Selecione a empresa para análise:", sorted(perfil["id"].unique()))
    
    # perfil_id = perfil[perfil["id"] == id_selecionado].iloc[0]
    # st.write(f"**Momento Atual:** {perfil_id['momento']} | **Margem Média:** {perfil_id['margem_med']:.1%}")
    
    # hist_empresa = base[base["id"] == id_selecionado].sort_values("ano_mes")
    # fig_line = px.line(hist_empresa, x="ano_mes", y=["receita", "despesa", "fluxo_liq"], title=f"Histórico Financeiro da Empresa {id_selecionado}")
    # st.plotly_chart(fig_line, use_container_width=True)
