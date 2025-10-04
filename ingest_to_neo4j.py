from neo4j import GraphDatabase
import pandas as pd

# --- 1. CONFIGURAÇÕES DE CONEXÃO ---
# Altere com as informações do seu banco de dados Neo4j
URI = "neo4j://127.0.0.1:7687"
AUTH = ("neo4j", "Billiedani1!") # Substitua "password" pela sua palavra-passe

# --- 2. CAMINHO DO SEU ARQUIVO DE DADOS ---
# --- AQUI ESTÁ A CORREÇÃO ---
# Removemos "data/" para que o script procure o ficheiro na pasta principal.
EXCEL_FILE_PATH = "Challenge FIAP - Bases.xlsx"
NOME_PLANILHA_EMPRESAS = "Base 1 - ID"
NOME_PLANILHA_TRANSACOES = "Base 2 - Transações"

def criar_constraints(tx):
    """
    Cria uma regra no banco de dados para garantir que não haverá
    empresas com o mesmo ID. Isto é crucial para a performance e integridade.
    """
    tx.run("CREATE CONSTRAINT unique_empresa_id IF NOT EXISTS FOR (e:Empresa) REQUIRE e.id IS UNIQUE")

def carregar_empresas(tx, empresas_records):
    """
    Carrega as empresas para o Neo4j. Cada empresa será um NÓ (um círculo) no grafo.
    A query usa MERGE para evitar duplicados.
    """
    query = """
    UNWIND $rows AS row
    MERGE (e:Empresa {id: row.id})
    SET e.data_abertura = date(row.dt_abrt),
        e.saldo = toFloat(row.vl_sldo),
        e.cnae = row.ds_cnae
    """
    tx.run(query, rows=empresas_records)

def carregar_transacoes(tx, transacoes_records):
    """
    Cria as RELAÇÕES (as setas) de pagamento entre as empresas.
    A query primeiro encontra o pagador e o recebedor e depois cria a relação :PAGOU_PARA.
    """
    query = """
    UNWIND $rows AS row
    MATCH (pagador:Empresa {id: row.id_pgto})
    MATCH (recebedor:Empresa {id: row.id_rcbe})
    CREATE (pagador)-[t:PAGOU_PARA {
        valor: toFloat(row.vl),
        tipo: row.ds_tran,
        data: date(row.dt_refe)
    }]->(recebedor)
    """
    tx.run(query, rows=transacoes_records)

# --- Função Principal de Execução ---
if __name__ == "__main__":
    print("A iniciar a ingestão de dados para o Neo4j...")
    
    # Carregar dados do Excel
    try:
        empresas_df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=NOME_PLANILHA_EMPRESAS, dtype={'id': str})
        trans_df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=NOME_PLANILHA_TRANSACOES, dtype={'id_pgto': str, 'id_rcbe': str})
    except FileNotFoundError:
        print(f"\nERRO CRÍTICO: O ficheiro '{EXCEL_FILE_PATH}' não foi encontrado.")
        print("Por favor, certifique-se de que o nome do ficheiro está correto e que ele está na pasta principal do projeto.")
        exit() # Termina o script se o ficheiro não for encontrado

    # Limpar e formatar datas para o formato do Neo4j (YYYY-MM-DD)
    empresas_df['dt_abrt'] = pd.to_datetime(empresas_df['dt_abrt']).dt.strftime('%Y-%m-%d')
    trans_df['dt_refe'] = pd.to_datetime(trans_df['dt_refe']).dt.strftime('%Y-%m-%d')
    
    empresas_records = empresas_df.to_dict('records')
    trans_records = trans_df.to_dict('records')
    
    # Conectar e popular o banco de dados
    try:
        with GraphDatabase.driver(URI, auth=AUTH) as driver:
            with driver.session(database="neo4j") as session:
                print("A limpar base de dados antiga...")
                session.run("MATCH (n) DETACH DELETE n")

                session.execute_write(criar_constraints)
                print("Constraint de unicidade criada.")
                
                session.execute_write(carregar_empresas, empresas_records)
                print(f"{len(empresas_records)} nós de Empresa carregados.")
                
                session.execute_write(carregar_transacoes, trans_records)
                print(f"{len(trans_records)} relações de Pagamento carregadas.")
                
        print("\nIngestão de dados concluída com sucesso!")
    except Exception as e:
        print(f"\nOcorreu um erro durante a conexão com o Neo4j: {e}")
        print("Verifique se o Neo4j Desktop está a correr e se as suas credenciais (URI, utilizador, palavra-passe) estão corretas.")