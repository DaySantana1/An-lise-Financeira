import streamlit as st
import pandas as pd
from pyvis.network import Network
import os
from neo4j import GraphDatabase
import networkx as nx
from networkx.algorithms import community as nx_comm
import random
from consulta_ia import gerar_resumo_executivo, gerar_resumo_individual_rede

# --- 1. CONFIGURAÇÕES ---
URI = "bolt://localhost:7687"
AUTH = ("neo4j", "Billiedani1!") # Verifique se esta é a sua palavra-passe correta

col1, col2, col3 = st.columns([1, 2, 1])

with col1:
    st.image("assets/logo.png")


st.set_page_config(page_title="Análise de Ecossistema", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .stAlert { border-radius: 10px; }
    .legend-color-box {
        width: 15px; height: 15px; display: inline-block; margin-right: 8px;
        border-radius: 3px; vertical-align: middle;
    }
    /* --- ESTILO PARA O NOSSO NOVO BOTÃO DE CÓPIA --- */
    .copy-button {
        background-color: #007bff; color: white; border: none;
        padding: 5px 10px; border-radius: 5px; cursor: pointer;
        margin-top: 10px; font-size: 12px;
    }
    .copy-button:hover {
        background-color: #0056b3;
    }
    
    div[data-testid="stImage"] {
        margin-top: 30px;
    }
</style>
""", unsafe_allow_html=True)



st.title("Painel de Análise de Interdependência do Ecossistema")
st.write("""
Navegue entre uma visão macro do **Ecossistema Geral** para identificar clusters e riscos sistémicos, 
ou mergulhe numa **Análise Individual** para um diagnóstico focado numa única empresa.
""")

# --- Funções de Consulta ao Neo4j ---
@st.cache_data
def get_lista_empresas(_driver):
    with _driver.session(database="neo4j") as session:
        result = session.run("MATCH (e:Empresa) RETURN e.id AS id ORDER BY id")
        return [record["id"] for record in result]

@st.cache_data
def get_top_conexoes(_driver, limite):
    query = """
    MATCH (p:Empresa)-[r:PAGOU_PARA]->(c:Empresa)
    RETURN p.id AS pagador, c.id AS recebedor, SUM(r.valor) AS valor_total
    ORDER BY valor_total DESC LIMIT $limite
    """
    with _driver.session(database="neo4j") as session:
        return pd.DataFrame(session.read_transaction(lambda tx: tx.run(query, limite=limite).data()))

@st.cache_data
def get_dependencias_criticas_geral(_driver, limiar_percentual):
    query = """
    MATCH (e:Empresa)<-[r:PAGOU_PARA]-(c:Empresa)
    WITH e, SUM(r.valor) AS receitaTotal
    MATCH (e)<-[r_ind:PAGOU_PARA]-(c_ind:Empresa)
    WITH e, receitaTotal, c_ind, SUM(r_ind.valor) AS valor_individual
    WHERE receitaTotal > 0 AND (valor_individual / receitaTotal) >= $limiar
    RETURN e.id AS empresa_dependente, c_ind.id AS cliente_chave, (valor_individual / receitaTotal) * 100 AS dependencia
    ORDER BY dependencia DESC LIMIT 10
    """
    with _driver.session(database="neo4j") as session:
        return pd.DataFrame(session.read_transaction(lambda tx: tx.run(query, limiar=limiar_percentual).data()))

@st.cache_data
def get_relacoes_individuais(_driver, empresa_id):
    query = """
    MATCH (empresa:Empresa {id: $empresa_id})
    OPTIONAL MATCH (cliente:Empresa)-[r:PAGOU_PARA]->(empresa)
    WITH empresa, cliente.id AS cliente_id, SUM(r.valor) AS valor_cliente
    WITH empresa, COLLECT({cliente: cliente_id, valor: valor_cliente}) AS clientes_data
    OPTIONAL MATCH (empresa)-[s:PAGOU_PARA]->(fornecedor:Empresa)
    WITH empresa, clientes_data, fornecedor.id AS fornecedor_id, SUM(s.valor) AS valor_fornecedor
    RETURN clientes_data, COLLECT({fornecedor: fornecedor_id, valor: valor_fornecedor}) AS fornecedores_data
    """
    with _driver.session(database="neo4j") as session:
        result = session.read_transaction(lambda tx: tx.run(query, empresa_id=empresa_id).single())
        
        clientes = [d for d in result['clientes_data'] if d['cliente'] is not None]
        df_clientes = pd.DataFrame(clientes)
        if not df_clientes.empty:
            total_receita = df_clientes['valor'].sum()
            df_clientes['dependencia_%'] = (df_clientes['valor'] / total_receita * 100) if total_receita > 0 else 0
            df_clientes = df_clientes.sort_values('dependencia_%', ascending=False).head(5)
        
        fornecedores = [d for d in result['fornecedores_data'] if d['fornecedor'] is not None]
        df_fornecedores = pd.DataFrame(fornecedores)
        if not df_fornecedores.empty:
            total_despesa = df_fornecedores['valor'].sum()
            df_fornecedores['dependencia_%'] = (df_fornecedores['valor'] / total_despesa * 100) if total_despesa > 0 else 0
            df_fornecedores = df_fornecedores.sort_values('dependencia_%', ascending=False).head(5)
            
        return df_clientes, df_fornecedores

@st.cache_data
def get_risco_em_cascata(_driver, top_cliente_id):
    if not top_cliente_id: return None
    query = """
    MATCH (cliente_foco:Empresa {id: $top_cliente_id})<-[r:PAGOU_PARA]-(cliente_do_cliente:Empresa)
    WITH cliente_foco, SUM(r.valor) AS receitaTotal
    MATCH (cliente_foco)<-[r_ind:PAGOU_PARA]-(cdc_ind:Empresa)
    WITH receitaTotal, cdc_ind, SUM(r_ind.valor) AS valor_individual
    RETURN cdc_ind.id AS cliente, (valor_individual / receitaTotal) * 100 AS dependencia
    ORDER BY dependencia DESC LIMIT 1
    """
    with _driver.session(database="neo4j") as session:
        result = session.read_transaction(lambda tx: tx.run(query, top_cliente_id=top_cliente_id).single())
        return pd.Series(result) if result else None

@st.cache_data
def get_vizinhanca(_driver, empresa_id):
    query = """
    MATCH (foco:Empresa {id: $empresa_id})
    OPTIONAL MATCH (foco)<-[r_in:PAGOU_PARA]-(cliente:Empresa)
    OPTIONAL MATCH (foco)-[r_out:PAGOU_PARA]->(fornecedor:Empresa)
    RETURN foco, COLLECT(DISTINCT {id: cliente.id, rel: r_in}) AS clientes, 
           COLLECT(DISTINCT {id: fornecedor.id, rel: r_out}) AS fornecedores
    """
    with _driver.session(database="neo4j") as session:
        return session.read_transaction(lambda tx: tx.run(query, empresa_id=empresa_id).single())

# --- Execução da Aplicação ---
try:
    driver = GraphDatabase.driver(URI, auth=AUTH)
    
    lista_empresas = get_lista_empresas(driver)
    opcoes_analise = ["Visão Geral do Ecossistema"] + lista_empresas
    selecao = st.selectbox("Selecione o tipo de análise:", opcoes_analise)

    st.markdown("---")

    if selecao == "Visão Geral do Ecossistema":
        st.header("Análise Macro do Ecossistema de Negócios")
        st.sidebar.header("Configurações da Análise Geral")
        limite_conexoes = st.sidebar.slider("Exibir as N conexões mais fortes:", 50, 500, 200, 25)
        limiar_risco = st.sidebar.slider("Limiar de Risco de Dependência (%)", 30, 100, 70, 5) / 100.0
        
        df_conexoes = get_top_conexoes(driver, limite_conexoes)
        df_risco_geral = get_dependencias_criticas_geral(driver, limiar_risco)
        
        if not df_conexoes.empty:
            G = nx.from_pandas_edgelist(df_conexoes, 'pagador', 'recebedor', edge_attr=['valor_total'], create_using=nx.DiGraph())
            communities = nx_comm.louvain_communities(G.to_undirected(), weight='valor_total', resolution=1.1)
            
            st.subheader("🤖 Resumo Executivo do Analista Virtual")
            with st.spinner("A IA está a analisar a rede e a gerar o resumo..."):
       
                resumo_ai = gerar_resumo_executivo(G, communities, limiar_risco, limite_conexoes, df_risco_geral)
                st.markdown(f'<div class="ai-summary" style="white-space: pre-wrap;">{resumo_ai}</div>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            st.subheader("🔍 Relações de Dependência Mais Críticas do Mercado")
            if not df_risco_geral.empty:
                st.dataframe(df_risco_geral, column_config={"dependencia": st.column_config.ProgressColumn("Dependência da Receita", format="%.1f%%")}, use_container_width=True, hide_index=True)
            else:
                st.info(f"Nenhuma relação de dependência acima de {limiar_risco:.0%} foi encontrada.")
            
            st.markdown("---")
            
        st.subheader("🕸️ Visualização do Ecossistema e seus Clusters")
        degree = dict(G.degree())
        node_community_map = {node: i for i, comm in enumerate(communities) for node in comm}
        
        # A paleta de cores é mantida para colorir os nós do grafo
        palette = [f"#{random.randint(0, 0xFFFFFF):06x}" for _ in range(len(communities))]
        
        with st.expander("Clique para explorar o grafo interativo", expanded=True):
            net = Network(height="700px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
            net.force_atlas_2based(gravity=-100, central_gravity=0.01, spring_length=200, spring_strength=0.08)
            max_degree = max(degree.values()) if degree else 1.0
            for node in G.nodes():
                community_id = node_community_map.get(node, -1)
                cor = palette[community_id % len(palette)] if community_id != -1 else "#808080"
                size = 10 + 40 * (degree.get(node, 0) / max_degree)
                net.add_node(node, label=node, color=cor, size=size, title=f"Cluster: {community_id}<br>Conexões: {degree.get(node, 0)}")
            for _, row in df_conexoes.iterrows():
                net.add_edge(row['pagador'], row['recebedor'], value=row['valor_total'], title=f"Valor: R$ {row['valor_total']:,.2f}", color="#dddddd")
            net.show_buttons(filter_=['physics'])
            path = "rede_temp.html"
            try:
                net.write_html(path, notebook=False)
                with open(path, "r", encoding="utf-8") as f:
                    st.components.v1.html(f.read(), height=750)
            finally:
                if os.path.exists(path): os.remove(path)

    else: 
        empresa_foco = selecao
        st.header(f"Análise Individual Estratégica: {empresa_foco}")
        
        resultado_relacoes = get_relacoes_individuais(driver, empresa_foco)
        top_clientes = resultado_relacoes[0]
        top_fornecedores = resultado_relacoes[1]
        
        cliente_principal = top_clientes.iloc[0] if not top_clientes.empty else None
        risco_cascata = get_risco_em_cascata(driver, cliente_principal['cliente']) if cliente_principal is not None else None

        st.subheader("🤖 Diagnóstico de Risco do Analista Virtual")
        with st.spinner("A IA está a analisar a cadeia de valor e a gerar recomendações..."):
            resumo_individual_ia = gerar_resumo_individual_rede(empresa_foco, top_clientes, top_fornecedores, risco_cascata)
            st.markdown(f'<div class="ai-summary" style="white-space: pre-wrap;">{resumo_individual_ia}</div>', unsafe_allow_html=True)

        st.markdown("---")
        
        st.subheader(f"🔍 Análise de Relações Diretas")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Clientes Mais Importantes**")
            st.dataframe(top_clientes.rename(columns={'cliente': 'Cliente', 'valor': 'Valor Recebido'}),
                         column_config={"dependencia_%": st.column_config.ProgressColumn("% da Receita", format="%.1f%%")},
                         use_container_width=True, hide_index=True)
        with col2:
            st.write("**Fornecedores Mais Importantes**")
            st.dataframe(top_fornecedores.rename(columns={'fornecedor': 'Fornecedor', 'valor': 'Valor Pago'}),
                         column_config={"dependencia_%": st.column_config.ProgressColumn("% da Despesa", format="%.1f%%")},
                         use_container_width=True, hide_index=True)


        st.markdown("---")

        st.subheader("🕸️ Visualização do Ecossistema Imediato")
        with st.expander("Clique para explorar o grafo de conexões da empresa"):
            resultado_vizinhanca = get_vizinhanca(driver, empresa_foco)
            net = Network(height="600px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)
            net.barnes_hut(gravity=-2000, spring_length=250)

            net.add_node(empresa_foco, label=empresa_foco, color='#ff4b4b', size=30, shape='star')
            
            for cliente_data in resultado_vizinhanca['clientes']:
                if cliente_data and cliente_data['id']:
                    cliente_id = cliente_data['id']; rel = cliente_data['rel']
                    net.add_node(cliente_id, label=cliente_id, color='#28a745', size=15)
                    net.add_edge(cliente_id, empresa_foco, value=rel['valor'], title=f"Valor: R$ {rel['valor']:,.2f}", width=max(1, rel['valor']/500000))
            
            for fornecedor_data in resultado_vizinhanca['fornecedores']:
                if fornecedor_data and fornecedor_data['id']:
                    fornecedor_id = fornecedor_data['id']; rel = fornecedor_data['rel']
                    net.add_node(fornecedor_id, label=fornecedor_id, color='#007bff', size=15)
                    net.add_edge(empresa_foco, fornecedor_id, value=rel['valor'], title=f"Valor: R$ {rel['valor']:,.2f}", width=max(1, rel['valor']/500000))

            net.show_buttons(filter_=['physics'])
            path = "rede_temp.html"
            try:
                net.write_html(path, notebook=False)
                with open(path, "r", encoding="utf-8") as f:
                    st.components.v1.html(f.read(), height=650)
            finally:
                if os.path.exists(path):
                    os.remove(path)

except Exception as e:
    st.error(f"Ocorreu um erro: {e}")