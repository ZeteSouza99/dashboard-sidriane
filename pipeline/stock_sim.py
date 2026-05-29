"""Simulação de estoque a partir do histórico de vendas.

Premissa (claramente comunicada na UI):
- Estoque inicial = vendas de 60 dias projetadas (cobertura alvo).
- Estoque atual = estoque inicial - unidades já vendidas no período observado.
- Valor estoque = unidades * preço unitário médio do produto.
- Status:
    CRÍTICO  cobertura < 15 dias
    BAIXO    15 <= cobertura < 30 dias
    OK       30 <= cobertura < 60 dias
    ALTO     cobertura >= 60 dias
"""
from __future__ import annotations
import numpy as np
import pandas as pd

DIAS_ALVO = 60


def simular(df: pd.DataFrame) -> pd.DataFrame:
    dias_observados = max((df["data"].max() - df["data"].min()).days + 1, 1)

    agg = df.groupby(["ean", "produto_canon"], as_index=False).agg(
        unidades_vendidas=("qtd", "sum"),
        valor_vendido=("valor", "sum"),
    )
    agg["preco_unit"] = agg["valor_vendido"] / agg["unidades_vendidas"]
    agg["vendas_diaria_media"] = agg["unidades_vendidas"] / dias_observados

    # estoque inicial: alvo de cobertura + ruído leve para realismo da simulação
    rng = np.random.default_rng(42)
    fator = rng.uniform(0.8, 1.6, size=len(agg))
    agg["estoque_inicial"] = np.ceil(agg["vendas_diaria_media"] * DIAS_ALVO * fator).astype(int)
    agg["unidades_estoque"] = (agg["estoque_inicial"] - agg["unidades_vendidas"]).clip(lower=0).astype(int)
    agg["valor_estoque"] = (agg["unidades_estoque"] * agg["preco_unit"]).round(2)
    agg["cobertura_dias"] = np.where(
        agg["vendas_diaria_media"] > 0,
        agg["unidades_estoque"] / agg["vendas_diaria_media"],
        np.inf,
    )

    def status(c):
        if c < 15: return "CRITICO"
        if c < 30: return "BAIXO"
        if c < 60: return "OK"
        return "ALTO"

    agg["status"] = agg["cobertura_dias"].apply(status)
    agg["cobertura_dias"] = agg["cobertura_dias"].replace(np.inf, 999).round(1)
    return agg.sort_values("valor_estoque", ascending=False)
