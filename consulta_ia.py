from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('API_KEY')
client = OpenAI(api_key=api_key)
df = pd.read_excel(f'Challenge FIAP - Bases.xlsx',sheet_name="Base 1 - ID")
df_2 = pd.read_excel(f'Challenge FIAP - Bases.xlsx',sheet_name="Base 2 - Transações")

def retorna_informacao_empresas(cnpj):
    df_cnpj = df[df['id'] == cnpj]
    context = df_cnpj.to_string(index=False)

    pergunta = (
        "Você deve analisar os dados da empresa apresentados a seguir. "
        f"Pegue as informações do dataframe {context}"

        "As colunas significam: "
        "id = identificador do CNPJ da empresa, "
        "vl_fatu = valor de faturamento, "
        "vl_sldo = valor de saldo disponível, "
        "dt_abrt = data de abertura da empresa, "
        "ds_cnae = setor econômico da empresa (descrição CNAE), "
        "dt_refe = data de referência dos dados.\n\n"
        "Com base exclusivamente nesses dados, escreva em um único parágrafo objetivo: "
        "1. Se a empresa aparenta estar em crescimento, estabilidade ou desaceleração considerando faturamento e saldo, pegue isso a partir da margem média calculada. "
        "2. Se o saldo está proporcional ao faturamento ou se há risco de desequilíbrio. "
        "3. Cite brevemente o setor de atuação (ds_cnae) e como isso pode influenciar o momento da empresa. "
        "Não invente dados que não estão presentes na tabela. "
        "Se não houver informações suficientes, declare isso claramente."
    )

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Dados da empresa:\n{context}"},
            {"role": "user", "content": pergunta}
        ]
    )

    return response.choices[0].message.content


def gerar_resumo_executivo(G, communities, limiar_risco, limite_conexoes, top_conexoes):
    """
    Gera um resumo executivo estratégico a partir dos dados da rede.
    Recebe grafo, comunidades, limiar de risco e conexões críticas.
    """
    total_empresas = G.number_of_nodes()
    total_conexoes = G.number_of_edges()
    num_clusters = len(communities)

    resumo_contexto = {
        "total_empresas": total_empresas,
        "total_conexoes": total_conexoes,
        "num_clusters": num_clusters,
        "limiar_risco": limiar_risco,
        "top_conexoes": top_conexoes[:5]  # envia só as 5 mais críticas
    }

    prompt = f"""
    Você é um analista de risco interno de um grande Banco.

    Dados resumidos da rede:
    {resumo_contexto}

    Tarefas:
    1. Analise a relevância estrutural da rede.
    2. Avalie riscos de dependência comparando com o limiar {limiar_risco:.0%}.
    3. Cite os maiores pontos críticos (se existirem) entre clientes e fornecedores.
    4. Elabore um **resumo executivo em tom estratégico**, direcionado para a diretoria.

    Formato:
    Retorne somente o resumo executivo em texto corrido, sem listas nem JSON.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # mais rápido e barato
        messages=[
            {"role": "system", "content": "Você é um analista de risco interno do Banco Santander."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=500
    )

    return response.choices[0].message.content.strip()