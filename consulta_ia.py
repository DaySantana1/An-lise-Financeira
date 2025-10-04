from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os
import streamlit as st

# --- Carregamento da Chave de API ---
load_dotenv()
api_key = os.getenv('API_KEY') or st.secrets.get("OPENAI_API_KEY")

if not api_key:
    st.error("Chave de API da OpenAI não encontrada. Por favor, configure o ficheiro .env ou os segredos do Streamlit.")
    client = None
else:
    client = OpenAI(api_key=api_key)

# --- Função para a página de Análise Individual (Mantida) ---
def retorna_informacao_empresas(perfil_empresa, media_setor):
    if not client: return "Cliente OpenAI não inicializado. Verifique a sua chave de API."
    
    contexto = f"""
    - ID da Empresa: {perfil_empresa['id']}
    - Momento (via ML): {perfil_empresa['momento']}
    - Setor (CNAE): {perfil_empresa['ds_cnae']}
    - Receita Média (6m): {perfil_empresa['receita_media_6m']:,.0f} BRL
    - Margem Média (6m): {perfil_empresa['margem_media_6m']:.1%}
    - Tendência de Crescimento (Receita 3m): {'Positiva' if perfil_empresa['crescimento_receita_3m'] > 0 else 'Negativa ou Estável'}
    - Média de Receita do Setor: {media_setor['receita_media_6m']:,.0f} BRL
    - Média de Margem do Setor: {media_setor['margem_media_6m']:.1%}
    """
    prompt = f"""
    Como um analista financeiro sênior do Banco Santander, analise os seguintes dados de uma empresa e do seu setor.
    **Dados Analisados:**
    {contexto}
    **Sua Tarefa:**
    Escreva um diagnóstico conciso em **um único parágrafo**. O diagnóstico deve:
    1.  Começar com o "Momento" da empresa e o que isso significa.
    2.  Comparar a receita e a margem da empresa com a média do seu setor.
    3.  Com base na tendência de crescimento, dar uma recomendação estratégica.
    Seja direto e foque em insights acionáveis para um gestor.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um analista financeiro sênior a escrever um diagnóstico para um cliente empresarial."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250, temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ocorreu um erro ao comunicar com a IA: {e}"

# --- Função para a página de Análise de Rede  ---
def gerar_resumo_executivo(G, communities, limiar_risco, limite_conexoes, relacoes_risco_df):
    """
    Gera um resumo executivo estratégico, agora num formato de dados puro,
    com cada insight numa nova linha, para garantir a formatação no Streamlit.
    """
    if not client:
        return "Cliente OpenAI não inicializado."

    total_empresas = G.number_of_nodes()
    num_clusters = len(communities)
    top_risco = relacoes_risco_df.iloc[0].to_dict() if not relacoes_risco_df.empty else None

    # --- PROMPT REFINADO PARA UM FORMATO DE DADOS PURO ---
    prompt = f"""
    Como analista de risco sênior, prepare um resumo para a diretoria com base nos dados abaixo.
    - Empresas na Análise: {total_empresas}
    - Clusters (Mercados) Identificados: {num_clusters}
    - Limiar de Risco Analisado: {limiar_risco:.0%}
    - Relação de Maior Risco: {top_risco if top_risco else "Nenhuma acima do limiar."}

    **Sua Tarefa:**
    Escreva um resumo em 3 parágrafos curtos.
    **Retorne APENAS os 3 parágrafos, um em cada nova linha. SEM títulos, SEM negrito, SEM bullet points, SEM separadores.**

    1. [Parágrafo sobre a descoberta mais importante dos {num_clusters} clusters.]
    2. [Parágrafo sobre a relação de maior risco encontrada ({top_risco}). Se não houver, afirme que o risco está controlado.]
    3. [Parágrafo com uma única recomendação acionável.]
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um analista de risco a preparar um briefing. Responda apenas com 3 parágrafos de texto, um por linha."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.4,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ocorreu um erro ao comunicar com a IA: {e}"

# --- FUNÇÃO ATUALIZADA PARA A PÁGINA DE PREVISÃO ---
def gerar_resumo_previsao(df_historico, df_previsao):
    """
    Gera uma análise de IA sobre a previsão de fluxo de caixa,
    identificando a tendência e sugerindo produtos financeiros de forma direta.
    """
    if not client:
        return "Cliente OpenAI não inicializado. Verifique a sua chave de API."

    fluxo_historico_medio = df_historico['fluxo_liq'].mean()
    fluxo_previsto_total = df_previsao['fluxo_liq'].sum()
    tendencia = "superavitário (sobra de caixa)" if fluxo_previsto_total > 0 else "deficitário (necessidade de caixa)"

    contexto = f"""
    **Análise de Fluxo de Caixa para uma Empresa Cliente**
    - Fluxo de Caixa Líquido Médio Histórico: {fluxo_historico_medio:,.0f} BRL
    - Fluxo de Caixa Líquido Total Previsto para os próximos {len(df_previsao)} meses: {fluxo_previsto_total:,.0f} BRL
    - Tendência Geral Prevista: {tendencia}
    """

    # --- PROMPT REFINADO PARA SER MAIS OBJETIVO ---
    prompt = f"""
    Como um analista financeiro do Banco Santander, analise o seguinte resumo de previsão de fluxo de caixa de um cliente.

    **Dados da Previsão:**
    {contexto}

    **Sua Tarefa:**
    Escreva uma recomendação curta e direta em **um único parágrafo**. A sua recomendação deve:
    1.  Interpretar a tendência prevista (superavitária ou deficitária).
    2.  Com base na tendência, sugerir um tipo de produto financeiro do Santander (investimento PJ para superavit, crédito PJ para deficit).
    
    **Seja direto e termine a sua resposta logo após a sugestão do produto. Não adicione frases de encerramento ou convites para discussão.**
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um analista financeiro a oferecer uma recomendação objetiva a um cliente PJ."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150, # Reduzido para garantir ainda mais concisão
            temperature=0.5,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ocorreu um erro ao comunicar com a IA: {e}"
    
# --- ANÁLISE DE REDE INDIVIDUAL ---
def gerar_resumo_individual_rede(empresa_foco, top_clientes, top_fornecedores, risco_cascata):
    """
    Gera uma análise de IA sobre a cadeia de valor de uma única empresa,
    focando em riscos de dependência e interdependência.
    """
    if not client:
        return "Cliente OpenAI não inicializado. Verifique a sua chave de API."

    # Prepara os dados de contexto para a IA
    cliente_principal = top_clientes.iloc[0].to_dict() if not top_clientes.empty else "Nenhum cliente significativo."
    fornecedor_principal = top_fornecedores.iloc[0].to_dict() if not top_fornecedores.empty else "Nenhum fornecedor significativo."

    contexto = f"""
    **Análise da Cadeia de Valor para a Empresa:** {empresa_foco}
    - **Cliente Principal:** {cliente_principal}
    - **Fornecedor Principal:** {fornecedor_principal}
    - **Análise de Risco em Cascata (Cliente do Cliente):** {risco_cascata.to_dict() if risco_cascata is not None and not risco_cascata.empty else "Risco indireto baixo ou não aplicável."}
    """

    prompt = f"""
    Como um especialista em risco de crédito do Banco Santander, analise os seguintes dados da cadeia de valor de um cliente.

    **Dados da Rede do Cliente:**
    {contexto}

    **Sua Tarefa:**
    Escreva um diagnóstico estratégico em **um único parágrafo conciso**. O diagnóstico deve:
    1.  Identificar o **principal ponto de vulnerabilidade** do cliente (seja um cliente ou fornecedor com alta dependência).
    2.  Comentar sobre o **risco em cascata**, se for relevante.
    3.  Sugerir proativamente uma **solução ou produto financeiro** do Santander para mitigar o principal risco identificado (ex: seguro de crédito para dependência de cliente, ou adiantamento a fornecedores para fortalecer a cadeia).

    Seja direto, focando na identificação do risco e na solução que o banco pode oferecer.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Você é um especialista em risco de crédito a preparar um diagnóstico para um cliente empresarial."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=250,
            temperature=0.6,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Ocorreu um erro ao comunicar com a IA: {e}"