import streamlit as st
import pandas as pd
import plotly.express as px
from data_loader import load_transacoes, load_empresas
from utils import features_cashflow, clusterizar_empresas_kmeans

st.set_page_config(page_title="Análise de Perfil das Empresas", layout="wide")

# --- CSS Customizado ---
# --- CSS Customizado (Aprimorado) ---
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .block-container {
        padding-top: 1rem;
    }
    div[data-testid="stImage"] {
        margin-top: 30px;
    }
</style>
""", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.image("assets/logo.png")

# --- Função de Cache para Carregar e Processar todos os Dados ---
@st.cache_data
def carregar_e_processar_dados_home():
    """
    Função centralizada para carregar, processar e preparar todas as
    bases de dados necessárias para as análises da Home.
    """
    trans = load_transacoes()
    empresas = load_empresas()
    base = features_cashflow(trans)
    perfil = clusterizar_empresas_kmeans(base, empresas.copy())
    return base, perfil, empresas, trans

base, perfil, empresas, trans = carregar_e_processar_dados_home()

# --- Título ---
st.title("Dashboard de Inteligência de Ecossistema")

# --- FILTRO DE SEGMENTAÇÃO POR CNAE ---
st.subheader("Filtro de Segmentação")
lista_cnae = sorted(perfil['ds_cnae'].unique())
opcoes_cnae = ["Todos os Setores"] + lista_cnae
cnae_selecionado = st.selectbox("Selecione um Setor (CNAE) para focar a análise:", opcoes_cnae)

# --- LÓGICA DE FILTRAGEM DOS DADOS ---
# Com base na seleção, filtramos os dataframes que serão usados nas análises
if cnae_selecionado == "Todos os Setores":
    perfil_filtrado_cnae = perfil
    trans_filtrado = trans
    empresas_filtrado = empresas
else:
    perfil_filtrado_cnae = perfil[perfil['ds_cnae'] == cnae_selecionado]
    ids_no_cnae = perfil_filtrado_cnae['id'].unique()
    trans_filtrado = trans[
        (trans['id_pgto'].isin(ids_no_cnae)) |
        (trans['id_rcbe'].isin(ids_no_cnae))
    ]
    empresas_filtrado = empresas[empresas['id'].isin(ids_no_cnae)]

st.markdown("---")

# --- KPIs (AGORA DINÂMICOS COM BASE NO FILTRO) ---
# AJUSTE: O header agora é dinâmico e os KPIs usam os dataframes filtrados
st.header(f"Indicadores-Chave: {cnae_selecionado}")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total de empresas analisadas", f"{perfil_filtrado_cnae['id'].nunique():,}")
with col2:
    if not perfil_filtrado_cnae.empty:
        maior_momento = perfil_filtrado_cnae['momento'].mode()[0]
        share = perfil_filtrado_cnae['momento'].value_counts(normalize=True).max()
        st.metric("Momento predominante (via ML)", maior_momento, f"{(share*100):.0f}% do total")
    else:
        st.metric("Momento predominante (via ML)", "N/A", "0%")
with col3:
    if not empresas_filtrado.empty:
        saldo_medio = empresas_filtrado.groupby("id")["vl_sldo"].last().mean()
        st.metric("Saldo médio por empresa", f"R$ {saldo_medio:,.0f}")
    else:
        st.metric("Saldo médio por empresa", "R$ 0")

st.markdown("---")

st.header("Visão Geral do Ecossistema")
c1, c2 = st.columns(2)

with c1:
    st.subheader("Distribuição por Momento (ML)")
    
    dist_momento = perfil_filtrado_cnae['momento'].value_counts().reset_index()
    
    # --- AQUI ESTÁ A MUDANÇA ---
    # Trocamos para um gráfico de barras HORIZONTAIS para melhor alinhamento e leitura
    fig_barras_h = px.bar(
        dist_momento,
        x='count',        # O valor numérico agora vai no eixo X
        y='momento',      # A categoria em texto vai no eixo Y
        orientation='h',  # Define a orientação para horizontal
        title="Contagem de Empresas por Fase",
        labels={'count': 'Nº de Empresas', 'momento': 'Momento da Empresa'},
        text='count'
    )
    
    # Garante que a maior barra fica no topo, para uma leitura mais fácil
    fig_barras_h.update_layout(yaxis={'categoryorder':'total ascending'})
    fig_barras_h.update_traces(textposition='outside')
    
    st.plotly_chart(fig_barras_h, use_container_width=True)
    st.caption("Este gráfico mostra a quantidade de empresas em cada fase do ciclo de vida, conforme classificado pelo modelo de Machine Learning.")

with c2:
    st.subheader("Clusters de Receita vs. Despesa")

    # O seu código para os sliders e o gráfico de dispersão permanece exatamente o mesmo
    if not perfil_filtrado_cnae.empty:
        max_receita = int(perfil_filtrado_cnae['receita_media_6m'].quantile(0.99))
        filtro_receita = st.slider(
            "Ajustar Eixo de Receita Média (R$)", 
            0, max_receita, (0, int(max_receita * 0.5))
        )

        max_despesa = int(perfil_filtrado_cnae['despesa_media_6m'].quantile(0.99))
        filtro_despesa = st.slider(
            "Ajustar Eixo de Despesa Média (R$)", 
            0, max_despesa, (0, int(max_despesa * 0.5))
        )

        perfil_filtrado_final = perfil_filtrado_cnae[
            (perfil_filtrado_cnae['receita_media_6m'] >= filtro_receita[0]) &
            (perfil_filtrado_cnae['receita_media_6m'] <= filtro_receita[1]) &
            (perfil_filtrado_cnae['despesa_media_6m'] >= filtro_despesa[0]) &
            (perfil_filtrado_cnae['despesa_media_6m'] <= filtro_despesa[1])
        ]

        fig_scatter = px.scatter(
            perfil_filtrado_final, x="receita_media_6m", y="despesa_media_6m",
            color="momento", hover_data=['id', 'ds_cnae', 'margem_media_6m'],
            title="Posicionamento das Empresas por Receita e Despesa",
            labels={"receita_media_6m": "Receita Média (R$)", "despesa_media_6m": "Despesa Média (R$)"}
        )
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Não há dados para exibir no gráfico de dispersão para este setor.")

st.markdown("---")

# --- Análises Agregadas (AGORA DINÂMICAS) ---
st.header("Análises Agregadas do Segmento")
col_agg1, col_agg2 = st.columns(2)

with col_agg1:
    st.subheader("Análise por Maturidade da Empresa")
    # AJUSTE: Usa o dataframe filtrado pelo CNAE
    if not perfil_filtrado_cnae.empty:
        bins = [0, 2, 5, 10, 100]
        labels = ['Startup (<2 anos)', 'Em Crescimento (2-5 anos)', 'Madura (5-10 anos)', 'Estabelecida (>10 anos)']
        perfil_filtrado_cnae['faixa_maturidade'] = pd.cut(perfil_filtrado_cnae['idade'], bins=bins, labels=labels, right=False)
        
        analise_maturidade = perfil_filtrado_cnae.groupby('faixa_maturidade', observed=True).agg(
            receita_media=('receita_media_6m', 'mean')
        ).reset_index()

        fig_maturidade = px.bar(
            analise_maturidade, x='faixa_maturidade', y='receita_media',
            title='Receita Média por Nível de Maturidade',
            labels={'receita_media': 'Receita Média (R$)', 'faixa_maturidade': 'Nível de Maturidade'},
            text='receita_media', color='faixa_maturidade'
        )
        fig_maturidade.update_traces(texttemplate='R$ %{text:,.0f}', textposition='outside')
        st.plotly_chart(fig_maturidade, use_container_width=True)
    else:
        st.info("Não há dados de maturidade para este setor.")

with col_agg2:
    st.subheader("Análise por Tipo de Transação")
    # AJUSTE: Usa o dataframe de transações filtrado
    if not trans_filtrado.empty:
        analise_transacoes = trans_filtrado.groupby('ds_tran')['vl'].sum().reset_index().sort_values('vl', ascending=False)
        
        fig_transacoes = px.pie(
            analise_transacoes.head(10), names='ds_tran', values='vl',
            title='Distribuição do Valor Total por Tipo de Transação (Top 10)', hole=0.4
        )
        st.plotly_chart(fig_transacoes, use_container_width=True)
    else:
        st.info("Não há transações para exibir para este setor.")

st.markdown("---")

# --- Análise por Setor (CNAE) - NÃO FOI ALTERADA ---
# Esta secção continua a usar o dataframe 'perfil' original para permitir a comparação
st.header("Análise Comparativa Entre Setores (CNAE)")
st.caption("Esta análise mostra sempre a visão completa para permitir a comparação entre os setores.")
analise_cnae = perfil.groupby('ds_cnae').agg(
    receita_total=('receita_media_6m', 'sum'),
    numero_empresas=('id', 'count')
).reset_index().sort_values('receita_total', ascending=False)
fig_cnae = px.bar(
    analise_cnae.head(15), x='receita_total', y='ds_cnae', orientation='h',
    title='Top 15 Setores por Receita Agregada',
    labels={'receita_total': 'Receita Total (R$)', 'ds_cnae': 'Setor'}, text='receita_total'
)
fig_cnae.update_traces(texttemplate='%{text:,.2s}', textposition='outside')
fig_cnae.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_cnae, use_container_width=True)



