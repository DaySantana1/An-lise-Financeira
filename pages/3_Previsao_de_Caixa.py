import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import load_transacoes
from utils import features_cashflow, prever_fluxo_caixa
from consulta_ia import gerar_resumo_previsao
import plotly.graph_objects as go

st.set_page_config(page_title="Previsão de Fluxo de Caixa", layout="wide")

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

# --- Função de Cache para Carregar os Dados ---
@st.cache_data
def carregar_dados_previsao():
    """Carrega e prepara os dados de base para a previsão."""
    trans = load_transacoes()
    base = features_cashflow(trans)
    return base

base = carregar_dados_previsao()

st.title("Forecasting: Previsão de Fluxo de Caixa")
st.write("""
Esta ferramenta utiliza um modelo para projetar as tendências futuras de 
receitas, despesas e fluxo de caixa, e oferece uma recomendação estratégica baseada na previsão.
""")

# --- Filtros ---
lista_empresas = sorted(base["id"].unique())
id_sel = st.selectbox("Selecione a empresa para a previsão:", lista_empresas)
periodos_previsao = st.slider("Selecione o número de meses para prever:", min_value=3, max_value=12, value=6, step=1)

if id_sel:
    # Filtra o histórico da empresa selecionada
    hist_id = base[base["id"] == id_sel].sort_values("ano_mes")
    
    # Faz a previsão para cada métrica
    previsao_receita = prever_fluxo_caixa(hist_id, 'receita', periodos_previsao)
    previsao_despesa = prever_fluxo_caixa(hist_id, 'despesa', periodos_previsao)
    
    # Combina as previsões e calcula o fluxo de caixa previsto
    df_previsao = pd.merge(previsao_receita, previsao_despesa, on='ano_mes')
    df_previsao['fluxo_liq'] = df_previsao['receita'] - df_previsao['despesa']
    
    st.markdown("---")

    # --- NOVA SEÇÃO: RECOMENDAÇÃO DO ANALISTA VIRTUAL ---
    st.header("🤖 Recomendação Estratégica do Analista Virtual")
    with st.spinner("A IA está a analisar a previsão e a gerar recomendações..."):
        # Chamamos a nossa nova função de IA com os dados calculados
        resumo_previsao_ia = gerar_resumo_previsao(hist_id, df_previsao)
        st.markdown(f'<div class="ai-summary" style="white-space: pre-wrap;">{resumo_previsao_ia}</div>', unsafe_allow_html=True)

    st.markdown("---")
    
    # --- KPIs da Previsão ---
    st.subheader(f"Resultados Previstos para os Próximos {periodos_previsao} Meses")
    col1, col2, col3 = st.columns(3)
    with col1:
        total_receita_prevista = df_previsao['receita'].sum()
        st.metric("Total de Receita Prevista", f"R$ {total_receita_prevista:,.0f}")
    with col2:
        total_despesa_prevista = df_previsao['despesa'].sum()
        st.metric("Total de Despesa Prevista", f"R$ {total_despesa_prevista:,.0f}")
    with col3:
        total_fluxo_previsto = df_previsao['fluxo_liq'].sum()
        st.metric("Fluxo de Caixa Líquido Previsto", f"R$ {total_fluxo_previsto:,.0f}", 
                  delta_color=("inverse" if total_fluxo_previsto < 0 else "normal"))
                  
    st.markdown("---")
    
    # --- Gráfico de Previsão ---
    st.subheader("Gráfico de Histórico vs. Previsão")
    
    # Prepara dataframes para o plot
    hist_id_plot = hist_id.copy()
    hist_id_plot['ano_mes'] = pd.to_datetime(hist_id_plot['ano_mes'])
    df_previsao_plot = df_previsao.copy()
    
    df_completo = pd.concat([hist_id_plot, df_previsao_plot])
    
    fig = px.line(
        hist_id_plot,
        x='ano_mes',
        y=['receita', 'despesa', 'fluxo_liq'],
        labels={"value": "Valor (R$)", "ano_mes": "Mês", "variable": "Métrica"},
        title=f"Histórico e Previsão para a Empresa {id_sel}"
    )

    for metrica, cor in zip(['receita', 'despesa', 'fluxo_liq'], px.colors.qualitative.Plotly):
        fig.add_trace(go.Scatter(
            x=df_previsao_plot['ano_mes'],
            y=df_previsao_plot[metrica],
            mode='lines',
            line=dict(color=cor, dash='dash'),
            name=f'{metrica} (Previsão)',
        ))

    ultima_data_historica = hist_id_plot['ano_mes'].max()
    fig.add_shape(
        type="line", x0=ultima_data_historica, x1=ultima_data_historica,
        y0=0, y1=1, yref="paper",
        line=dict(color="grey", width=2, dash="dash")
    )
    fig.add_annotation(
        x=ultima_data_historica, y=0.95, yref="paper",
        showarrow=False, xanchor="left", text="Início da Previsão"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.caption("Nota: As previsões são baseadas num modelo de regressão linear simples e representam uma extrapolação da tendência histórica.")