import streamlit as st
import pandas as pd
import networkx as nx
from networkx.algorithms import community as nx_comm
from pyvis.network import Network
import os
import random
from consulta_ia import gerar_resumo_executivo

st.set_page_config(page_title="Cadeia de Valor", layout="wide")

# --- CSS Customizado ---
st.markdown("""
<style>
    div[data-testid="metric-container"] {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .block-container {
        padding-top: 2rem;
    }
    .ai-summary {
        background-color: #e8f0fe;
        border-left: 5px solid #1a73e8;
        padding: 15px;
        border-radius: 5px;
        margin-bottom: 2rem;
    }
            
    /* Texto dos valores dos elementos */
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] div {
        color: #000000 !important;
    }

</style>
""", unsafe_allow_html=True)

st.title("Dashboard Avançado da Cadeia de Valor")
st.write("""
Este painel revela a estrutura do ecossistema de negócios. Comece com o **Resumo Executivo** para insights rápidos, 
aprofunde-se nas análises de **Risco**, **Resiliência**, e explore livremente a rede no **Grafo Interativo**.
""")

# --- Carregamento dos Dados ---
@st.cache_data
def carregar_dados_completos():
    try:
        from data_loader import load_transacoes, load_empresas
        trans = load_transacoes()
        empresas = load_empresas()
        return trans, empresas
    except (ModuleNotFoundError, ImportError):
        st.error("Arquivo 'data_loader.py' não encontrado.")
        return pd.DataFrame(), pd.DataFrame()

trans, empresas = carregar_dados_completos()

if trans.empty or empresas.empty:
    st.error("Dados de transações ou empresas não encontrados.")
else:
    # --- Barra Lateral de Filtros ---
    st.sidebar.header("Configurações da Análise")
    peso_aresta = st.sidebar.selectbox("Analisar conexões por:", ["Valor Total Transacionado", "Número de Transações"])
    print(peso_aresta)
    limite_conexoes = st.sidebar.slider("Analisar as N conexões mais fortes:", 50, 1000, 250, 50)
    print(limite_conexoes)
    limiar_risco = st.sidebar.slider("Limiar de Risco de Dependência (%)", 10, 100, 50, 5) / 100.0
    print(limiar_risco)

    # --- Processamento e Criação do Grafo ---
    if peso_aresta == "Valor Total Transacionado":
        agg_edges = trans.groupby(['id_pgto', 'id_rcbe'])['vl'].sum().reset_index().rename(columns={'vl': 'weight'})
    else:
        agg_edges = trans.groupby(['id_pgto', 'id_rcbe']).size().reset_index(name='weight')
    top_edges = agg_edges.sort_values('weight', ascending=False).head(limite_conexoes)
    G = nx.from_pandas_edgelist(top_edges, 'id_pgto', 'id_rcbe', ['weight'], create_using=nx.DiGraph())

    if G.number_of_nodes() > 0:
        # --- LÓGICA DE ANÁLISE E NOMEAÇÃO DOS CLUSTERS ---
        try:
            communities = list(nx_comm.louvain_communities(G.to_undirected(), weight='weight', resolution=1.2))
            node_community_map = {node: i for i, comm in enumerate(communities) for node in comm}
            
            df_nodes = pd.DataFrame(node_community_map.items(), columns=['id', 'cluster_id'])
            df_nodes = df_nodes.merge(empresas[['id', 'ds_cnae']], on='id', how='left')
            cluster_names = df_nodes.groupby('cluster_id')['ds_cnae'].agg(lambda x: x.mode().iloc[0] if not x.empty and not x.mode().empty else f"Cluster {x.name}").to_dict()

        except Exception as e:
            st.warning(f"Não foi possível detectar comunidades. Erro: {e}")
            communities = []
            cluster_names = {}
            node_community_map = {}

        # --- CÁLCULO DE RISCO DE CONCENTRAÇÃO ---
        total_receita = trans.groupby('id_rcbe')['vl'].sum().rename('total_receita')
        total_despesa = trans.groupby('id_pgto')['vl'].sum().rename('total_despesa')
        
        # agg_edges completo para o cálculo de risco
        dependencia_df_completo = trans.groupby(['id_pgto', 'id_rcbe'])['vl'].sum().reset_index().rename(columns={'vl': 'weight'})
        dependencia_df_completo = dependencia_df_completo.merge(total_receita, left_on='id_rcbe', right_index=True, how='left')
        dependencia_df_completo = dependencia_df_completo.merge(total_despesa, left_on='id_pgto', right_index=True, how='left')
        
        dependencia_df_completo['dependencia_receita'] = (dependencia_df_completo['weight'] / dependencia_df_completo['total_receita']).fillna(0)
        dependencia_df_completo['dependencia_despesa'] = (dependencia_df_completo['weight'] / dependencia_df_completo['total_despesa']).fillna(0)
        
        relacoes_de_risco = dependencia_df_completo[
            (dependencia_df_completo['dependencia_receita'] >= limiar_risco) | 
            (dependencia_df_completo['dependencia_despesa'] >= limiar_risco)
        ]

        # --- Resumo Executivo com IA ---
        st.header("🤖 Resumo Executivo do Analista Virtual")
        with st.container():
            st.markdown('<div class="ai-summary">', unsafe_allow_html=True)
            total_empresas = G.number_of_nodes()
            total_conexoes = G.number_of_edges()
            num_clusters = len(communities)
            
            st.write(f"A análise da rede, composta por **{total_empresas} empresas** e **{total_conexoes} conexões** (com base nos filtros), revela os seguintes insights:")
            
            if communities:
                st.markdown(f"- **Estrutura do Mercado:** O ecossistema está organizado em **{num_clusters} clusters** (mercados) distintos.")
            
            reciprocal_edges = [ (u, v) for u, v in G.edges() if G.has_edge(v, u) and u < v ]
            if reciprocal_edges:
                st.markdown(f"- **Relações Estratégicas:** Foram identificadas **{len(reciprocal_edges)} parcerias estratégicas** (relações de mão dupla).")

            degree = dict(G.degree())
            if degree:
                empresa_mais_conectada, num_conexoes = max(degree.items(), key=lambda item: item[1])
                st.markdown(f"- **Player-Chave:** A empresa **{empresa_mais_conectada}** emerge como o ator mais central na rede filtrada, com **{num_conexoes} parceiros**.")
            
            st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # ---ANÁLISE DE RISCO DE CONCENTRAÇÃO ---
        st.header("Análise de Risco de Concentração")
        st.write(f"Exibindo relações onde um parceiro representa mais de **{limiar_risco:.0%}** do total de receitas ou despesas.")

        col_risco1, col_risco2 = st.columns(2)
        with col_risco1:
            st.subheader("⚠️ Empresas Dependentes de Clientes")
            risco_clientes = relacoes_de_risco[relacoes_de_risco['dependencia_receita'] >= limiar_risco]
            st.dataframe(
                risco_clientes[['id_rcbe', 'id_pgto', 'dependencia_receita']]
                .rename(columns={'id_rcbe': 'Empresa Dependente', 'id_pgto': 'Cliente-Chave', 'dependencia_receita': '% da Receita Total'})
                .sort_values('% da Receita Total', ascending=False).head(10),
                column_config={"% da Receita Total": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1)},
                use_container_width=True, hide_index=True
            )

        with col_risco2:
            st.subheader("⚠️ Empresas Dependentes de Fornecedores")
            risco_fornecedores = relacoes_de_risco[relacoes_de_risco['dependencia_despesa'] >= limiar_risco]
            st.dataframe(
                risco_fornecedores[['id_pgto', 'id_rcbe', 'dependencia_despesa']]
                .rename(columns={'id_pgto': 'Empresa Dependente', 'id_rcbe': 'Fornecedor-Chave', 'dependencia_despesa': '% da Despesa Total'})
                .sort_values('% da Despesa Total', ascending=False).head(10),
                column_config={"% da Despesa Total": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=1)},
                use_container_width=True, hide_index=True
            )
        
        st.markdown("---")
        
        # --- ANÁLISES DE RESILIÊNCIA E PARCERIAS ---
        st.header("Análises de Resiliência e Parcerias Estratégicas")
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Análise de Resiliência: Mais Clientes")
            num_clientes = G.in_degree()
            df_clientes = pd.DataFrame(dict(num_clientes).items(), columns=['Empresa', 'Nº de Clientes'])
            st.dataframe(df_clientes.sort_values('Nº de Clientes', ascending=False).head(10), use_container_width=True, hide_index=True)
            st.caption("Empresas com receita mais diversificada.")
        with col2:
            st.subheader("Análise de Resiliência: Mais Fornecedores")
            num_fornecedores = G.out_degree()
            df_fornecedores = pd.DataFrame(dict(num_fornecedores).items(), columns=['Empresa', 'Nº de Fornecedores'])
            st.dataframe(df_fornecedores.sort_values('Nº de Fornecedores', ascending=False).head(10), use_container_width=True, hide_index=True)
            st.caption("Empresas com menor risco na cadeia de suprimentos.")

        st.subheader("Parcerias Estratégicas Detalhadas (Relações de Mão Dupla)")
        if reciprocal_edges:
            parcerias = []
            for u, v in reciprocal_edges:
                parcerias.append({"Parceiro A": u, "Parceiro B": v})
            st.dataframe(pd.DataFrame(parcerias), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma parceria recíproca encontrada com os filtros atuais.")
        
        st.markdown("---")
        
        # --- FERRAMENTA DE EXPLORAÇÃO VISUAL ---
        with st.expander("Clique aqui para explorar o grafo interativo de clusters", expanded=True):
            net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#1f2430", directed=True)
            max_degree = max(degree.values()) if degree else 1.0
            palette = ["#%06x" % random.randint(0, 0xFFFFFF) for _ in range(len(communities))]

            for node_id in G.nodes():
                size = 15 + 50 * (degree.get(node_id, 0) / max_degree)
                community_id = node_community_map.get(node_id, -1)
                color = palette[community_id] if community_id != -1 and community_id < len(palette) else "#808080"
                cluster_name = cluster_names.get(community_id, "Sem Cluster")
                title = f"<b>Empresa:</b> {node_id}<br><b>Cluster:</b> {cluster_name}"
                net.add_node(node_id, label=str(node_id), value=size, title=title, color=color)
            
            for _, row in top_edges.iterrows():
                net.add_edge(row['id_pgto'], row['id_rcbe'], value=row['weight'], color="rgba(200, 200, 200, 0.5)")

            net.show_buttons(filter_=['physics'])
            
            path = "rede_temp.html"
            try:
                net.write_html(path, notebook=False)
                with open(path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                st.components.v1.html(html_content, height=850, scrolling=True)
            finally:
                if os.path.exists(path):
                    os.remove(path)
    else:
        st.info("Nenhum dado para exibir com os filtros selecionados.")
    
    st.header("📊 Resumo Executivo com IA")
    with st.container():
        st.markdown('<div class="ai-summary">', unsafe_allow_html=True)

        # calcula top conexões (já está pronto no seu código como top_edges)
        top_conexoes = top_edges.to_dict(orient="records")

        resumo_ai = gerar_resumo_executivo(G, communities, limiar_risco, limite_conexoes, top_conexoes)
        st.write(resumo_ai)

        st.markdown('</div>', unsafe_allow_html=True)

