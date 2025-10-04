import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import load_transacoes, load_empresas
from utils import features_cashflow, clusterizar_empresas_kmeans
from consulta_ia import retorna_informacao_empresas
import plotly.graph_objects as go

st.set_page_config(page_title="Análise Individual da Empresa", layout="wide")

# --- CSS Customizado para o resumo da IA ---
st.markdown("""
<style>
    .ai-summary {
        background-color: #e8f0fe;
        border-left: 5px solid #1a73e8;
        padding: 20px;
        border-radius: 8px;
        margin-bottom: 2rem;
        font-size: 1.1em;
        line-height: 1.6;
            
    }
    div[data-testid="stImage"] {
        margin-top: 0px;
    }
</style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.image("assets/logo.png")

# --- Função de Cache para Carregar e Processar todos os Dados ---
@st.cache_data
def carregar_e_processar_dados():
    """
    Função centralizada que carrega os dados e executa o pipeline de ML para esta página.
    """
    trans = load_transacoes()
    empresas = load_empresas()
    base = features_cashflow(trans)
    perfil_clusterizado = clusterizar_empresas_kmeans(base, empresas.copy())
    return trans, base, perfil_clusterizado

trans, base, perfil = carregar_e_processar_dados()

st.title("Diagnóstico Individual e Benchmarking Competitivo")

# --- Filtro Único e Centralizado ---
if perfil.empty:
    st.error("Não foi possível carregar os dados para análise.")
else:
    ids_unicos = sorted(perfil["id"].unique())
    id_sel = st.selectbox("Selecione a empresa para análise:", ids_unicos)

    # --- Toda a análise acontece DEPOIS da seleção ---
    if id_sel:
        # Extração dos dados da empresa selecionada
        perfil_id = perfil[perfil["id"] == id_sel].iloc[0]
        cnae_id = perfil_id['ds_cnae']
        hist_id = base[base["id"] == id_sel].sort_values("ano_mes")
        media_setor = perfil[perfil['ds_cnae'] == cnae_id][['receita_media_6m', 'margem_media_6m']].mean()

        # --- NOVA SEÇÃO: DIAGNÓSTICO DO ANALISTA VIRTUAL ---
        st.header("🤖 Diagnóstico do Analista Virtual")
        with st.spinner("A IA está a analisar os dados e a gerar o diagnóstico..."):
            # Chamamos a nossa função de IA com os dados já calculados
            diagnostico_ia = retorna_informacao_empresas(perfil_id, media_setor)
            st.markdown(f'<div class="ai-summary" style="white-space: pre-wrap;">{diagnostico_ia}</div>', unsafe_allow_html=True)
        
        st.markdown("---")

        # --- KPIs e Informações Chave ---
        st.subheader(f"Visão Geral Detalhada: {id_sel}")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Momento da Empresa (via ML)", perfil_id['momento'])
        with col2:
            st.metric("Margem Média (6m)", f"{perfil_id['margem_media_6m']:.1%}")

        st.markdown("---")

        # --- Seção de Benchmarking Competitivo ---
        st.subheader(f"Benchmarking Competitivo (vs. Setor: {cnae_id})")
        col_bench1, col_bench2 = st.columns(2)
        with col_bench1:
            delta_receita = perfil_id['receita_media_6m'] - media_setor['receita_media_6m']
            st.metric(
                label="Receita Média da Empresa vs. Média do Setor",
                value=f"R$ {perfil_id['receita_media_6m']:,.0f}",
                delta=f"R$ {delta_receita:,.0f}"
            )
            st.caption(f"Média do setor: R$ {media_setor['receita_media_6m']:,.0f}")
        with col_bench2:
            delta_margem = perfil_id['margem_media_6m'] - media_setor['margem_media_6m']
            st.metric(
                label="Margem Média da Empresa vs. Média do Setor",
                value=f"{perfil_id['margem_media_6m']:.1%}",
                delta=f"{delta_margem:.1%}"
            )
            st.caption(f"Média do setor: {media_setor['margem_media_6m']:.1%}")

        st.markdown("---")

        # --- ANÁLISE: APROXIMAÇÃO COM O FLUXO DE CAIXA (REGRESSÃO LINEAR) ---
        st.subheader("Análise de Tendências do Fluxo de Caixa")
        hist_id['ano_mes'] = pd.to_datetime(hist_id['ano_mes'])
        df_melted = hist_id.melt(id_vars=['ano_mes'], value_vars=['receita', 'despesa', 'fluxo_liq'], var_name='Métrica', value_name='Valor')

        fig_regressao = px.scatter(
            df_melted, x='ano_mes', y='Valor', color='Métrica',
            trendline="ols", title="Tendência de Receitas, Despesas e Fluxo de Caixa",
            labels={"Valor": "Valor (R$)", "ano_mes": "Mês"}
        )
        st.plotly_chart(fig_regressao, use_container_width=True)

        st.markdown("---")

        # --- ANÁLISE: DISTRIBUIÇÃO DE RECEITAS E DESPESAS ---
        st.subheader("Composição Detalhada de Receitas e Despesas")
        col_dist1, col_dist2 = st.columns(2)

        def plotar_distribuicao_barras(df_trans, empresa_id, tipo, coluna_id, titulo, cor):
            mix = (df_trans[df_trans[coluna_id] == empresa_id]
                   .groupby("ds_tran")["vl"].sum()
                   .sort_values(ascending=False).reset_index())
            
            total = mix["vl"].sum()
            mix["percentual"] = (mix["vl"] / total) * 100 if total > 0 else 0

            fig = go.Figure(go.Bar(
                y=mix['ds_tran'], x=mix['vl'],
                text=mix.apply(lambda row: f" R$ {row['vl']:,.0f} ({row['percentual']:.1f}%)", axis=1),
                textposition='auto', orientation='h', marker_color=cor
            ))
            fig.update_layout(
                title_text=titulo,
                xaxis_title='Valor Total (R$)', yaxis_title=f'Categoria de {tipo}',
                yaxis=dict(autorange="reversed"), height=400, margin=dict(l=10, r=10, t=30, b=10)
            )
            return fig

        with col_dist1:
            st.plotly_chart(
                plotar_distribuicao_barras(trans, id_sel, 'Receita', 'id_rcbe', 'Distribuição de Receitas por Origem', 'mediumseagreen'),
                use_container_width=True
            )
            
        with col_dist2:
            st.plotly_chart(
                plotar_distribuicao_barras(trans, id_sel, 'Despesa', 'id_pgto', 'Distribuição de Despesas por Categoria', 'indianred'),
                use_container_width=True
            )