import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LinearRegression

def features_cashflow(trans):
    """
    Cria as features de fluxo de caixa mensais a partir dos dados brutos de transações.
    """
    df = trans.copy()
    df['dt_refe'] = pd.to_datetime(df['dt_refe'])
    df['ano_mes'] = df['dt_refe'].dt.to_period('M').astype(str)
    recebimentos = df.groupby(['id_rcbe', 'ano_mes'])['vl'].sum().reset_index().rename(columns={'id_rcbe': 'id', 'vl': 'receita'})
    pagamentos = df.groupby(['id_pgto', 'ano_mes'])['vl'].sum().reset_index().rename(columns={'id_pgto': 'id', 'vl': 'despesa'})
    base = pd.merge(recebimentos, pagamentos, on=['id', 'ano_mes'], how='outer').fillna(0)
    base['fluxo_liq'] = base['receita'] - base['despesa']
    base['margem'] = base['fluxo_liq'] / base['receita'].replace(0, np.nan)
    base['margem'] = base['margem'].fillna(0)
    return base.sort_values(['id', 'ano_mes'])

def _calcular_tendencia(serie):
    """Função auxiliar para calcular a tendência de crescimento via regressão linear."""
    if len(serie) < 2: return 0
    x = np.arange(len(serie)).reshape(-1, 1)
    y = serie.values.reshape(-1, 1)
    modelo = LinearRegression().fit(x, y)
    return modelo.coef_[0][0]

def _criar_features_para_cluster(base, empresas):
    """
    Prepara o "DNA" de cada empresa, calculando as métricas (features)
    que serão usadas pelo modelo de Machine Learning para encontrar os grupos.
    """
    # Esta função mantém as suas personalizações de diagnóstico
    print("\n--- INICIANDO DIAGNÓSTICO EM _criar_features_para_cluster ---")
    try:
        print("PASSO 1: Verificando colunas recebidas no DataFrame 'base':")
        print(base.columns.tolist())

        perfil_financeiro = base.groupby('id').agg(
            receita_media_6m=('receita', lambda x: x.tail(6).mean()),
            despesa_media_6m=('despesa', lambda x: x.tail(6).mean()),
            crescimento_receita_3m=('receita', lambda x: _calcular_tendencia(x.tail(3))),
            margem_media_6m=('margem', lambda x: x.tail(6).mean()),
            volatilidade_receita=('receita', lambda x: x.tail(6).std())
        ).reset_index()

        print("\nPASSO 2: Colunas criadas em 'perfil_financeiro' (depois do .agg()):")
        print(perfil_financeiro.columns.tolist())

        data_referencia = pd.to_datetime('2024-01-01')
        empresas_copy = empresas.copy()
        
        print("\nPASSO 3: Verificando colunas recebidas no DataFrame 'empresas':")
        print(empresas_copy.columns.tolist())
        
        empresas_copy['idade'] = (data_referencia - empresas_copy['dt_abrt']).dt.days / 365.25
        
        perfil_completo = pd.merge(perfil_financeiro, empresas_copy[['id', 'idade', 'ds_cnae']].drop_duplicates(subset='id'), on='id', how='left')
        
        print("\nPASSO 4: Colunas em 'perfil_completo' (depois do merge):")
        print(perfil_completo.columns.tolist())

        perfil_completo.fillna(0, inplace=True)
        perfil_completo.replace([np.inf, -np.inf], 0, inplace=True)
        
        print("\nPASSO 5: Processamento dentro da função concluído com sucesso.")
        print("--- FIM DO DIAGNÓSTICO --- \n")
        
        return perfil_completo

    except Exception as e:
        print(f"\n\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print(f"!!!!!! OCORREU UM ERRO GRAVE DENTRO DE _criar_features_para_cluster !!!!!!")
        import traceback
        print("!!!!!! O traceback real do erro é:                          !!!!!!")
        print(traceback.format_exc())
        print(f"!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n\n")
        raise e

def clusterizar_empresas_kmeans(base, empresas):
    """
    Executa o pipeline de Machine Learning para encontrar e nomear os clusters de empresas.
    """
    df_features = _criar_features_para_cluster(base, empresas)
    features_para_modelo = df_features[['idade', 'receita_media_6m', 'despesa_media_6m', 'crescimento_receita_3m', 'margem_media_6m', 'volatilidade_receita']]
    
    scaler = StandardScaler()
    features_padronizadas = scaler.fit_transform(features_para_modelo)
    
    kmeans = KMeans(n_clusters=4, random_state=42, n_init='auto')
    df_features['cluster'] = kmeans.fit_predict(features_padronizadas)
    
    df_analise_clusters = df_features.groupby('cluster')[['idade', 'crescimento_receita_3m', 'margem_media_6m', 'receita_media_6m']].mean().sort_values('receita_media_6m').reset_index()
    
    nomes_clusters = {
        df_analise_clusters.loc[0, 'cluster']: 'Início',
        df_analise_clusters.loc[1, 'cluster']: 'Declínio',
        df_analise_clusters.loc[2, 'cluster']: 'Crescimento',
        df_analise_clusters.loc[3, 'cluster']: 'Maturidade'
    }
    
    df_features['momento'] = df_features['cluster'].map(nomes_clusters)
    return df_features

# --- FUNÇÃO RESTAURADA PARA A PÁGINA DE PREVISÃO ---
def prever_fluxo_caixa(serie_historica, metrica, periodos_futuros=6):
    """
    Prevê valores futuros para uma métrica financeira usando regressão linear.
    """
    df_historico = serie_historica[['ano_mes', metrica]].copy()
    df_historico['ano_mes'] = pd.to_datetime(df_historico['ano_mes'])
    # Cria um índice numérico para o tempo (número de dias desde o início)
    df_historico['time_idx'] = (df_historico['ano_mes'] - df_historico['ano_mes'].min()).dt.days

    # Treina o modelo de regressão linear
    modelo = LinearRegression()
    X = df_historico[['time_idx']]
    y = df_historico[metrica]
    modelo.fit(X, y)

    # Prepara os "pontos no futuro" para fazer a previsão
    ultimo_idx = df_historico['time_idx'].max()
    ultima_data = df_historico['ano_mes'].max()
    
    # Cria os índices e datas futuros
    indices_futuros = [ultimo_idx + 30 * i for i in range(1, periodos_futuros + 1)]
    datas_futuras = [ultima_data + pd.DateOffset(months=i) for i in range(1, periodos_futuros + 1)]
    
    # Faz a previsão para os pontos futuros
    previsoes = modelo.predict(pd.DataFrame(indices_futuros, columns=['time_idx']))

    # Retorna um dataframe com as previsões
    return pd.DataFrame({'ano_mes': datas_futuras, metrica: previsoes})