import pandas as pd
import streamlit as st

# --- CONFIGURAÇÃO PRINCIPAL ---
# Nome do seu arquivo Excel. Ele deve estar na mesma pasta que o Home.py
EXCEL_FILE_PATH = "Challenge FIAP - Bases.xlsx"

# Nomes exatos das suas planilhas
NOME_PLANILHA_EMPRESAS = "Base 1 - ID"
NOME_PLANILHA_TRANSACOES = "Base 2 - Transações"
# -----------------------------


@st.cache_data
def load_empresas():
    """
    Carrega e prepara o dataset de empresas a partir da planilha do Excel.
    """
    try:
        # Lê a planilha especificada do arquivo Excel
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=NOME_PLANILHA_EMPRESAS)
        
        # --- Validação de Colunas Essenciais ---
        # Verifique se os nomes das colunas no seu Excel correspondem a estes
        colunas_necessarias = ['id', 'dt_abrt', 'dt_refe', 'vl_fatu', 'vl_sldo', 'ds_cnae']
        for col in colunas_necessarias:
            if col not in df.columns:
                st.error(f"Coluna '{col}' não encontrada na planilha de empresas '{NOME_PLANILHA_EMPRESAS}'. Verifique seu arquivo Excel.")
                return pd.DataFrame()

        # Converte as colunas de data
        df['dt_abrt'] = pd.to_datetime(df['dt_abrt'])
        df['dt_refe'] = pd.to_datetime(df['dt_refe'])
        return df
        
    except FileNotFoundError:
        st.error(f"Arquivo Excel '{EXCEL_FILE_PATH}' não encontrado. Verifique o nome e se o arquivo está na pasta correta.")
        return pd.DataFrame()
    except ValueError as e:
        if f"Worksheet named '{NOME_PLANILHA_EMPRESAS}' not found" in str(e):
            st.error(f"Planilha com o nome '{NOME_PLANILHA_EMPRESAS}' não encontrada no arquivo Excel. Verifique o nome da sua planilha de empresas.")
        else:
            st.error(f"Erro ao ler a planilha de empresas: {e}")
        return pd.DataFrame()


@st.cache_data
def load_transacoes():
    """
    Carrega e prepara o dataset de transações a partir da planilha do Excel.
    """
    try:
        # Lê a planilha especificada do arquivo Excel
        df = pd.read_excel(EXCEL_FILE_PATH, sheet_name=NOME_PLANILHA_TRANSACOES)

        # --- Validação de Colunas Essenciais ---
        # Verifique se os nomes das colunas no seu Excel correspondem a estes
        colunas_necessarias = ['id_pgto', 'id_rcbe', 'vl', 'dt_refe', 'ds_tran']
        for col in colunas_necessarias:
            if col not in df.columns:
                st.error(f"Coluna '{col}' não encontrada na planilha de transações '{NOME_PLANILHA_TRANSACOES}'. Verifique seu arquivo Excel.")
                return pd.DataFrame()

        # Converte a coluna de data
        df['dt_refe'] = pd.to_datetime(df['dt_refe'])
        return df

    except FileNotFoundError:
        st.error(f"Arquivo Excel '{EXCEL_FILE_PATH}' não encontrado. Verifique o nome e se o arquivo está na pasta correta.")
        return pd.DataFrame()
    except ValueError as e:
        if f"Worksheet named '{NOME_PLANILHA_TRANSACOES}' not found" in str(e):
            st.error(f"Planilha com o nome '{NOME_PLANILHA_TRANSACOES}' não encontrada no arquivo Excel. Verifique o nome da sua planilha de transações.")
        else:
            st.error(f"Erro ao ler a planilha de transações: {e}")
        return pd.DataFrame()

