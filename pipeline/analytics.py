"""Analytics: KPIs, agregações, projeção (sklearn) e segmentação (KMeans).

Grava:
- web/data.json  -> alimenta o dashboard
- web/charts/*.png -> visualizações matplotlib estáticas
"""
from __future__ import annotations
import json
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from .config import PROCESSED_DIR, WEB_DIR
from . import stock_sim
from . import charts as charts_mod


HORIZON_DIAS = 14


# --------------------------- helpers ---------------------------

def _money(x): return round(float(x), 2)
def _int(x): return int(x)


# --------------------------- KPIs ---------------------------

def kpis(df: pd.DataFrame) -> dict:
    total = float(df["valor"].sum())
    unid = int(df["qtd"].sum())
    cnpjs = int(df["cnpj"].nunique())
    n_tx = int(len(df))
    dias = int(df["data"].nunique())
    return {
        "vendas_total": _money(total),
        "unidades": unid,
        "ticket_medio": _money(total / max(cnpjs, 1)),
        "ticket_transacao": _money(total / max(n_tx, 1)),
        "preco_medio_unitario": _money(total / max(unid, 1)),
        "unidades_por_transacao": round(unid / max(n_tx, 1), 2),
        "positivacao": cnpjs,
        "produtos_ativos": _int(df["ean"].nunique()),
        "vendedores": _int(df["vendedor"].nunique()),
        "canais": _int(df["canal"].nunique()),
        "ufs": _int(df["uf"].nunique()),
        "transacoes": n_tx,
        "dias_com_venda": dias,
        "vendas_dia_medio": _money(total / max(dias, 1)),
        "unidades_dia_medio": round(unid / max(dias, 1), 2),
        "transacoes_dia_medio": round(n_tx / max(dias, 1), 2),
    }


def kpis_highlights(df: pd.DataFrame) -> dict:
    """Destaques: melhor dia/semana/mês, melhor vendedor/produto/canal/UF, concentrações."""
    total = float(df["valor"].sum()) or 1.0

    def _peak(series_df, label_col):
        if series_df.empty:
            return {label_col: None, "valor": 0.0}
        row = series_df.loc[series_df["valor"].idxmax()]
        d = row[label_col]
        if hasattr(d, "strftime"):
            d = d.strftime("%Y-%m-%d")
        return {label_col: d, "valor": _money(row["valor"]), "qtd": int(row.get("qtd", 0))}

    dia = _peak(daily_sales(df), "data")
    sem = _peak(weekly_sales(df), "data")
    mes = _peak(monthly_sales(df), "data")

    bv = df.groupby("vendedor")["valor"].sum().sort_values(ascending=False)
    bp = df.groupby("produto_canon")["valor"].sum().sort_values(ascending=False)
    bc = df.groupby("canal")["valor"].sum().sort_values(ascending=False)
    bu = df.groupby("uf")["valor"].sum().sort_values(ascending=False)

    top10_prod = bp.head(10).sum()
    top1_cli = df.groupby("cnpj")["valor"].sum().sort_values(ascending=False).head(10).sum()

    return {
        "melhor_dia": dia,
        "melhor_semana": sem,
        "melhor_mes": mes,
        "melhor_vendedor": {"nome": bv.index[0] if len(bv) else None, "valor": _money(bv.iloc[0]) if len(bv) else 0},
        "melhor_produto": {"nome": bp.index[0] if len(bp) else None, "valor": _money(bp.iloc[0]) if len(bp) else 0},
        "melhor_canal":   {"nome": bc.index[0] if len(bc) else None, "valor": _money(bc.iloc[0]) if len(bc) else 0},
        "melhor_uf":      {"nome": bu.index[0] if len(bu) else None, "valor": _money(bu.iloc[0]) if len(bu) else 0},
        "concentracao_top10_produtos_pct": round(100 * top10_prod / total, 2),
        "concentracao_top10_clientes_pct": round(100 * top1_cli / total, 2),
        "share_top1_vendedor_pct": round(100 * bv.iloc[0] / total, 2) if len(bv) else 0,
        "share_top1_canal_pct":    round(100 * bc.iloc[0] / total, 2) if len(bc) else 0,
        "share_top1_uf_pct":       round(100 * bu.iloc[0] / total, 2) if len(bu) else 0,
    }


# --------------------------- agregações ---------------------------

def daily_sales(df: pd.DataFrame) -> pd.DataFrame:
    d = df.groupby("data", as_index=False).agg(
        valor=("valor", "sum"), qtd=("qtd", "sum"),
        transacoes=("valor", "size"), clientes=("cnpj", "nunique"),
    )
    return d.sort_values("data")


def weekly_sales(df: pd.DataFrame) -> pd.DataFrame:
    s = df.copy()
    s["periodo"] = s["data"].dt.to_period("W-SUN").dt.start_time
    g = s.groupby("periodo", as_index=False).agg(
        valor=("valor", "sum"), qtd=("qtd", "sum"),
        transacoes=("valor", "size"), clientes=("cnpj", "nunique"),
    ).sort_values("periodo")
    g = g.rename(columns={"periodo": "data"})
    return g


def monthly_sales(df: pd.DataFrame) -> pd.DataFrame:
    s = df.copy()
    s["periodo"] = s["data"].dt.to_period("M").dt.start_time
    g = s.groupby("periodo", as_index=False).agg(
        valor=("valor", "sum"), qtd=("qtd", "sum"),
        transacoes=("valor", "size"), clientes=("cnpj", "nunique"),
    ).sort_values("periodo")
    g = g.rename(columns={"periodo": "data"})
    return g


def clientes_detalhe(df: pd.DataFrame, top_n_produto: int = 1) -> pd.DataFrame:
    """Um registro por CNPJ com KPIs e top produto mais comprado (em valor)."""
    ref = df["data"].max()

    base = df.groupby("cnpj").agg(
        cliente=("cliente", lambda s: s.dropna().mode().iat[0] if not s.dropna().empty else ""),
        uf=("uf", lambda s: s.dropna().mode().iat[0] if not s.dropna().empty else ""),
        canal=("canal", lambda s: s.dropna().mode().iat[0] if not s.dropna().empty else ""),
        vendedor=("vendedor", lambda s: s.dropna().mode().iat[0] if not s.dropna().empty else ""),
        valor_total=("valor", "sum"),
        unidades=("qtd", "sum"),
        transacoes=("valor", "size"),
        dias_ativos=("data", "nunique"),
        n_produtos=("ean", "nunique"),
        primeira_compra=("data", "min"),
        ultima_compra=("data", "max"),
    )
    base["recency_dias"] = (ref - base["ultima_compra"]).dt.days
    base["ticket_medio"] = (base["valor_total"] / base["transacoes"]).round(2)

    # top produto por CNPJ (em valor)
    prod = (
        df.groupby(["cnpj", "produto_canon"], as_index=False)["valor"].sum()
          .sort_values(["cnpj", "valor"], ascending=[True, False])
          .groupby("cnpj").head(top_n_produto)
    )
    top_map = prod.groupby("cnpj")["produto_canon"].first().rename("top_produto")
    top_val = prod.groupby("cnpj")["valor"].first().rename("top_produto_valor")
    base = base.join(top_map).join(top_val)

    base = base.reset_index()
    base["valor_total"] = base["valor_total"].round(2)
    base["top_produto_valor"] = base["top_produto_valor"].round(2)
    return base.sort_values("valor_total", ascending=False)


def by_vendedor(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["valor"].sum()) or 1.0
    g = df.groupby("vendedor")
    out = g.agg(
        valor=("valor", "sum"),
        qtd=("qtd", "sum"),
        clientes=("cnpj", "nunique"),
        transacoes=("valor", "size"),
        dias_ativos=("data", "nunique"),
        produtos=("ean", "nunique"),
        ufs=("uf", "nunique"),
        canais=("canal", "nunique"),
    ).reset_index()
    out["ticket_medio"] = (out["valor"] / out["clientes"].clip(lower=1)).round(2)
    out["ticket_transacao"] = (out["valor"] / out["transacoes"].clip(lower=1)).round(2)
    out["preco_medio_unit"] = (out["valor"] / out["qtd"].clip(lower=1)).round(2)
    out["share_pct"] = (100 * out["valor"] / total).round(2)
    # melhor canal/uf/produto por vendedor
    def _top(group_col, value_col="valor"):
        s = df.groupby(["vendedor", group_col])[value_col].sum().reset_index()
        idx = s.groupby("vendedor")[value_col].idxmax()
        return s.loc[idx].set_index("vendedor")[group_col]
    out["melhor_canal"] = out["vendedor"].map(_top("canal"))
    out["melhor_uf"] = out["vendedor"].map(_top("uf"))
    out["melhor_produto"] = out["vendedor"].map(_top("produto_canon"))
    out["valor"] = out["valor"].round(2)
    return out.sort_values("valor", ascending=False)


def by_canal(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["valor"].sum()) or 1.0
    g = df.groupby("canal")
    out = g.agg(
        valor=("valor", "sum"),
        qtd=("qtd", "sum"),
        clientes=("cnpj", "nunique"),
        transacoes=("valor", "size"),
        vendedores=("vendedor", "nunique"),
        produtos=("ean", "nunique"),
        ufs=("uf", "nunique"),
    ).reset_index()
    out["ticket_medio"] = (out["valor"] / out["clientes"].clip(lower=1)).round(2)
    out["preco_medio_unit"] = (out["valor"] / out["qtd"].clip(lower=1)).round(2)
    out["share_pct"] = (100 * out["valor"] / total).round(2)
    out["valor"] = out["valor"].round(2)
    return out.sort_values("valor", ascending=False)


def by_uf(df: pd.DataFrame) -> pd.DataFrame:
    total = float(df["valor"].sum()) or 1.0
    g = df.groupby("uf")
    out = g.agg(
        valor=("valor", "sum"),
        qtd=("qtd", "sum"),
        clientes=("cnpj", "nunique"),
        transacoes=("valor", "size"),
        vendedores=("vendedor", "nunique"),
        produtos=("ean", "nunique"),
    ).reset_index()
    out["ticket_medio"] = (out["valor"] / out["clientes"].clip(lower=1)).round(2)
    out["preco_medio_unit"] = (out["valor"] / out["qtd"].clip(lower=1)).round(2)
    out["share_pct"] = (100 * out["valor"] / total).round(2)
    out["valor"] = out["valor"].round(2)
    return out.sort_values("valor", ascending=False)


def top_produtos(df: pd.DataFrame, n: int = 30) -> pd.DataFrame:
    total = float(df["valor"].sum()) or 1.0
    g = df.groupby(["ean", "produto_canon"])
    out = g.agg(
        valor=("valor", "sum"),
        qtd=("qtd", "sum"),
        clientes=("cnpj", "nunique"),
        transacoes=("valor", "size"),
        ufs=("uf", "nunique"),
        vendedores=("vendedor", "nunique"),
        canais=("canal", "nunique"),
    ).reset_index()
    out["preco_medio_unit"] = (out["valor"] / out["qtd"].clip(lower=1)).round(2)
    out["share_pct"] = (100 * out["valor"] / total).round(2)
    out["valor"] = out["valor"].round(2)
    return out.sort_values("valor", ascending=False).head(n)


def positivacao_por_vendedor(df: pd.DataFrame) -> pd.DataFrame:
    total_cnpjs = max(df["cnpj"].nunique(), 1)
    g = df.groupby("vendedor")
    out = g.agg(
        clientes_ativos=("cnpj", "nunique"),
        dias_com_venda=("data", "nunique"),
        valor=("valor", "sum"),
        qtd=("qtd", "sum"),
        transacoes=("valor", "size"),
        ufs=("uf", "nunique"),
        produtos=("ean", "nunique"),
    ).reset_index()
    out["valor_por_cliente"] = (out["valor"] / out["clientes_ativos"].clip(lower=1)).round(2)
    out["unidades_por_cliente"] = (out["qtd"] / out["clientes_ativos"].clip(lower=1)).round(2)
    out["transacoes_por_cliente"] = (out["transacoes"] / out["clientes_ativos"].clip(lower=1)).round(2)
    out["share_carteira_pct"] = (100 * out["clientes_ativos"] / total_cnpjs).round(2)
    out["valor"] = out["valor"].round(2)
    return out.sort_values("clientes_ativos", ascending=False)


def positivacao_extras(df: pd.DataFrame) -> dict:
    """Positivação cruzada: por UF/canal/mês, novos vs recorrentes, inativos."""
    ref = df["data"].max()
    por_uf = (
        df.groupby("uf")
          .agg(cnpjs=("cnpj", "nunique"), valor=("valor", "sum"))
          .reset_index().sort_values("cnpjs", ascending=False)
    )
    por_uf["valor"] = por_uf["valor"].round(2)
    por_canal = (
        df.groupby("canal")
          .agg(cnpjs=("cnpj", "nunique"), valor=("valor", "sum"))
          .reset_index().sort_values("cnpjs", ascending=False)
    )
    por_canal["valor"] = por_canal["valor"].round(2)
    por_mes = (
        df.assign(mes=df["data"].dt.to_period("M").dt.start_time)
          .groupby("mes").agg(cnpjs=("cnpj", "nunique"), valor=("valor", "sum"))
          .reset_index().sort_values("mes")
    )
    por_mes["valor"] = por_mes["valor"].round(2)

    cli_dias = df.groupby("cnpj")["data"].agg(["min", "max", "nunique"])
    novos = int(((ref - cli_dias["min"]).dt.days <= 7).sum())
    recorrentes = int((cli_dias["nunique"] > 1).sum())
    inativos_30d = int(((ref - cli_dias["max"]).dt.days > 30).sum())
    one_shot = int((cli_dias["nunique"] == 1).sum())

    return {
        "por_uf": df_to_records(por_uf),
        "por_canal": df_to_records(por_canal),
        "por_mes": df_to_records(por_mes),
        "resumo": {
            "total_cnpjs": int(len(cli_dias)),
            "novos_7d": novos,
            "recorrentes": recorrentes,
            "compra_unica": one_shot,
            "inativos_30d": inativos_30d,
        },
    }


# --------------------------- projeção (sklearn) ---------------------------

def projetar_vendas(daily: pd.DataFrame, horizon: int = HORIZON_DIAS) -> pd.DataFrame:
    """Regressão linear (sklearn) sobre dias x valor diário + banda de confiança."""
    daily = daily.copy().sort_values("data")
    daily["dia_idx"] = np.arange(len(daily))

    X = daily[["dia_idx"]].values
    y = daily["valor"].values
    model = LinearRegression().fit(X, y)
    pred_in = model.predict(X)
    resid = y - pred_in
    resid_std = float(np.std(resid))

    last_date = daily["data"].max()
    future_idx = np.arange(len(daily), len(daily) + horizon).reshape(-1, 1)
    future_dates = [last_date + timedelta(days=i + 1) for i in range(horizon)]
    yhat = model.predict(future_idx)
    band = 1.5 * resid_std

    proj = pd.DataFrame({
        "data": future_dates,
        "valor_proj": np.clip(yhat, 0, None),
        "lower": np.clip(yhat - band, 0, None),
        "upper": yhat + band,
        "moving_avg_7d": daily["valor"].tail(7).mean(),
    })
    return proj


def projecao_metricas(daily: pd.DataFrame, proj: pd.DataFrame) -> dict:
    """R², MAE, MAPE do ajuste in-sample + totais projetados."""
    if daily.empty or len(daily) < 2:
        return {}
    X = np.arange(len(daily)).reshape(-1, 1)
    y = daily["valor"].values
    model = LinearRegression().fit(X, y)
    pred = model.predict(X)
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    r2 = 1 - ss_res / ss_tot
    mae = float(np.mean(np.abs(y - pred)))
    nz = y != 0
    mape = float(np.mean(np.abs((y[nz] - pred[nz]) / y[nz])) * 100) if nz.any() else 0.0
    total_proj = float(proj["valor_proj"].sum()) if not proj.empty else 0.0
    return {
        "r2": round(r2, 4),
        "mae": _money(mae),
        "mape_pct": round(mape, 2),
        "slope_dia": _money(float(model.coef_[0])),
        "intercepto": _money(float(model.intercept_)),
        "horizonte_dias": int(len(proj)),
        "total_projetado": _money(total_proj),
        "media_diaria_projetada": _money(total_proj / max(len(proj), 1)),
        "min_projetado": _money(float(proj["lower"].sum())) if not proj.empty else 0,
        "max_projetado": _money(float(proj["upper"].sum())) if not proj.empty else 0,
    }


# --------------------------- segmentação (KMeans) ---------------------------

def segmentar_clientes(df: pd.DataFrame, k: int = 4) -> pd.DataFrame:
    """RFM-like: Recency, Frequency, Monetary -> KMeans."""
    ref = df["data"].max()
    rfm = df.groupby("cnpj").agg(
        recency=("data", lambda s: (ref - s.max()).days),
        frequency=("data", "nunique"),
        monetary=("valor", "sum"),
    )
    if len(rfm) < k:
        return pd.DataFrame()

    X = StandardScaler().fit_transform(rfm.values)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(X)
    rfm["cluster"] = km.labels_

    summary = rfm.groupby("cluster").agg(
        n_clientes=("monetary", "size"),
        recency_media=("recency", "mean"),
        freq_media=("frequency", "mean"),
        valor_medio=("monetary", "mean"),
        valor_total=("monetary", "sum"),
    ).reset_index()

    # rótulo qualitativo simples
    summary = summary.sort_values("valor_medio", ascending=False).reset_index(drop=True)
    labels = ["Campeões", "Leais", "Em desenvolvimento", "Em risco"]
    summary["label"] = [labels[i] if i < len(labels) else f"Cluster {i}" for i in range(len(summary))]
    for c in ["recency_media", "freq_media", "valor_medio", "valor_total"]:
        summary[c] = summary[c].round(2)
    return summary


# --------------------------- export ---------------------------

def df_to_records(df: pd.DataFrame) -> list:
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d")
    return out.to_dict(orient="records")


def main():
    print("[Analytics] Carregando consolidado...")
    df = pd.read_parquet(PROCESSED_DIR / "vendas.parquet")

    if df.empty:
        payload = {
            "empty": True,
            "meta": {
                "gerado_em": datetime.now().isoformat(timespec="seconds"),
                "data_min": None, "data_max": None,
                "notas": ["Nenhum arquivo carregado. Faça upload para visualizar os números."],
            },
        }
        out = WEB_DIR / "data.json"
        out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("[Analytics] estado vazio gravado.")
        return

    print("[Analytics] Calculando KPIs e agregações...")
    daily = daily_sales(df)
    proj = projetar_vendas(daily) if len(daily) >= 2 else pd.DataFrame(
        columns=["data", "valor_proj", "lower", "upper", "moving_avg_7d"]
    )
    estoque = stock_sim.simular(df)
    segm = segmentar_clientes(df)

    payload = {
        "empty": False,
        "meta": {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "data_min": df["data"].min().strftime("%Y-%m-%d"),
            "data_max": df["data"].max().strftime("%Y-%m-%d"),
            "horizonte_projecao_dias": HORIZON_DIAS,
            "notas": [
                "Vendedor derivado da origem do arquivo (cada planilha = distribuidor regional).",
                "Estoque é SIMULADO a partir do histórico (cobertura alvo 60 dias).",
                "Projeção: LinearRegression (scikit-learn) com banda de ±1.5σ dos resíduos.",
            ],
        },
        "kpis": kpis(df),
        "highlights": kpis_highlights(df),
        "daily_sales": df_to_records(daily),
        "weekly_sales": df_to_records(weekly_sales(df)),
        "monthly_sales": df_to_records(monthly_sales(df)),
        "projection": df_to_records(proj),
        "projection_metrics": projecao_metricas(daily, proj),
        "by_vendedor": df_to_records(by_vendedor(df)),
        "by_canal": df_to_records(by_canal(df)),
        "by_uf": df_to_records(by_uf(df)),
        "top_produtos": df_to_records(top_produtos(df, 30)),
        "positivacao_por_vendedor": df_to_records(positivacao_por_vendedor(df)),
        "positivacao_extras": positivacao_extras(df),
        "estoque": df_to_records(estoque.head(50)),
        "estoque_resumo": {
            "unidades_totais": int(estoque["unidades_estoque"].sum()),
            "valor_total": _money(estoque["valor_estoque"].sum()),
            "skus": int(len(estoque)),
            "criticos": int((estoque["status"] == "CRITICO").sum()),
            "baixos": int((estoque["status"] == "BAIXO").sum()),
            "ok": int((estoque["status"] == "OK").sum()),
            "alto": int((estoque["status"] == "ALTO").sum()),
            "valor_critico": _money(estoque.loc[estoque["status"] == "CRITICO", "valor_estoque"].sum()),
            "valor_baixo": _money(estoque.loc[estoque["status"] == "BAIXO", "valor_estoque"].sum()),
            "valor_ok": _money(estoque.loc[estoque["status"] == "OK", "valor_estoque"].sum()),
            "valor_alto": _money(estoque.loc[estoque["status"] == "ALTO", "valor_estoque"].sum()),
            "cobertura_media_dias": round(float(estoque["cobertura_dias"].mean()), 1),
        },
        "segmentacao": df_to_records(segm) if not segm.empty else [],
        "clientes": df_to_records(clientes_detalhe(df)),
    }

    out = WEB_DIR / "data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Analytics] {out.relative_to(WEB_DIR.parent)} ({out.stat().st_size/1024:.1f} KB)")

    print("[Analytics] Gerando gráficos matplotlib...")
    charts_mod.gerar_todos(df, daily, proj, by_vendedor(df), by_canal(df), top_produtos(df, 10))
    print("[Analytics] OK")


if __name__ == "__main__":
    main()
