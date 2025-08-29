import pandas as pd
import numpy as np
from sklearn.cluster import KMeans

def features_cashflow(trans_df):
    """
    Calcula features de fluxo de caixa (receita, despesa, fluxo líquido) por empresa e mês.
    """
    trans_df['ano_mes'] = trans_df['dt_refe'].dt.to_period('M').astype(str)
    receita = trans_df.groupby(['id_rcbe', 'ano_mes'])['vl'].sum().reset_index().rename(columns={'id_rcbe': 'id', 'vl': 'receita'})
    despesa = trans_df.groupby(['id_pgto', 'ano_mes'])['vl'].sum().reset_index().rename(columns={'id_pgto': 'id', 'vl': 'despesa'})
    base = pd.merge(receita, despesa, on=['id', 'ano_mes'], how='outer').fillna(0)
    base['fluxo_liq'] = base['receita'] - base['despesa']
    return base

def classificar_momento(base_df, window=3):
    """
    Classifica o momento financeiro da empresa com uma lógica mais adaptativa.
    """
    df = base_df.copy().sort_values(['id', 'ano_mes'])
    
    # Calcula métricas móveis para suavizar
    df['receita_mm'] = df.groupby('id')['receita'].transform(lambda x: x.rolling(window, min_periods=1).mean())
    df['fluxo_liq_mm'] = df.groupby('id')['fluxo_liq'].transform(lambda x: x.rolling(window, min_periods=1).mean())
    
    # Calcula a tendência recente (inclinação da reta dos últimos 'window' pontos)
    def get_tendencia(series):
        y = series.values
        x = np.arange(len(y))
        if len(x) < 2: return 0
        slope, _ = np.polyfit(x, y, 1)
        return slope / (series.mean() if series.mean() != 0 else 1) # Normaliza pela média

    df['tendencia_receita'] = df.groupby('id')['receita_mm'].transform(lambda x: x.rolling(window).apply(get_tendencia, raw=False)).fillna(0)
    df['tendencia_fluxo'] = df.groupby('id')['fluxo_liq_mm'].transform(lambda x: x.rolling(window).apply(get_tendencia, raw=False)).fillna(0)
    
    df['margem'] = (df['fluxo_liq'] / df['receita']).replace([np.inf, -np.inf], 0).fillna(0)

    # Pega o último registro de cada empresa
    perfil = df.groupby('id').last()
    perfil['margem_med'] = df.groupby('id')['margem'].mean()

    # Define limites de tendência com base em quantis (mais adaptativo)
    q_receita = perfil['tendencia_receita'].quantile([0.33, 0.66])
    q_fluxo = perfil['tendencia_fluxo'].quantile([0.33, 0.66])

    # Classificação do momento
    conditions = [
        (perfil['tendencia_receita'] > q_receita.iloc[1]) & (perfil['tendencia_fluxo'] > q_fluxo.iloc[1]),
        (perfil['tendencia_receita'] < q_receita.iloc[0]),
        (perfil['fluxo_liq_mm'] < 0) & (perfil['tendencia_fluxo'] < q_fluxo.iloc[0]),
        (perfil['tendencia_receita'].between(q_receita.iloc[0], q_receita.iloc[1]))
    ]
    choices = ['Expansão', 'Desacelerando', 'Retração', 'Estável']
    perfil['momento'] = np.select(conditions, choices, default='Observação')
    
    return perfil.reset_index()

def cluster_receita_despesa(perfil_df, n_clusters=4):
    """
    Clusteriza empresas com base na receita e despesa.
    """
    if perfil_df.empty or 'receita' not in perfil_df.columns:
        return pd.DataFrame(), None
    features = perfil_df[['receita', 'despesa']].fillna(0)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    perfil_df['cluster'] = kmeans.fit_predict(features)
    perfil_df.rename(columns={'receita': 'cx_receita', 'despesa': 'cx_despesa'}, inplace=True)
    return perfil_df, kmeans
