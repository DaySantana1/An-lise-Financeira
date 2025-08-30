from openai import OpenAI
import pandas as pd
from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('API_KEY')
client = OpenAI(api_key=api_key)

def retorna_informacao(cnpj):
    df = pd.read_excel(f'Challenge FIAP - Bases.xlsx',sheet_name="Base 1 - ID")
    df_cnpj = df[df['id'] == cnpj]
    context = df_cnpj.to_string()

    pergunta = "Faça um resumo em 1 paragráfo de uma forma sucinta sobre o momento da empresa, se ela esta crescendo ou desacelerando a partir do saldo que está sendo apresentado mas de forma geral"

    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": f"Você tem acesso aos seguintes dados da aba: {context}"},
            {"role": "user", "content": f"{pergunta}"}
        ]
    )


    return response.choices[0].message.content