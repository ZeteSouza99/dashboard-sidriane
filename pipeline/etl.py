"""ETL: lê 6 planilhas xlsx, normaliza schema e produz consolidado.

Trata:
- Datas em formato datetime, string dd/mm/yyyy e serial Excel.
- Colunas com nomes/posições diferentes por arquivo.
- EAN ausente (Tapajós RO) -> usa hash do nome do produto.
- Deduplicação por (cnpj, data, ean, valor, qtd).
- Canonização de nomes de produto via EAN.
"""
from __future__ import annotations
import re
import unicodedata
import numpy as np
import pandas as pd

from .config import FILES, RAW_DIR, PROCESSED_DIR, STD_COLUMNS


# --------------------------- helpers ---------------------------

EXCEL_EPOCH = pd.Timestamp("1899-12-30")


def parse_date(v):
    """Converte valor heterogêneo -> Timestamp. Aceita serial Excel."""
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return pd.NaT
    if isinstance(v, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(v)
    # tenta float (serial Excel)
    try:
        f = float(v)
        if 20000 < f < 80000:
            return EXCEL_EPOCH + pd.Timedelta(days=f)
    except (TypeError, ValueError):
        pass
    return pd.to_datetime(v, dayfirst=True, errors="coerce")


def slugify(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_").upper()
    return s


# --------------------------- core ---------------------------

def standardize(df: pd.DataFrame, mapping: dict, vendedor: str, fonte: str) -> pd.DataFrame:
    """Aplica um mapping (field -> col_name) a um DataFrame bruto.

    Mapping pode vir do dicionário manual (config.FILES) ou do classificador ML.
    Campos ausentes recebem fallback razoável.
    """
    m = mapping
    out = pd.DataFrame()

    out["cliente"] = (
        df[m["cliente"]].astype(str).str.strip()
        if m.get("cliente") else df[m["cnpj"]].astype(str)
    )
    out["cnpj"] = df[m["cnpj"]].astype(str).str.replace(r"\D", "", regex=True).str.zfill(14)
    out["uf"] = df[m["uf"]].astype(str).str.strip().str.upper() if m.get("uf") else "??"
    out["data"] = df[m["data"]].apply(parse_date)
    if m.get("ean"):
        out["ean"] = pd.to_numeric(df[m["ean"]], errors="coerce").astype("Int64").astype(str)
    else:
        out["ean"] = df[m["produto"]].apply(lambda p: "SYN_" + slugify(p)[:24])
    out["produto"] = df[m["produto"]].astype(str).str.strip()
    out["valor"] = pd.to_numeric(df[m["valor"]], errors="coerce").fillna(0.0)
    out["qtd"] = pd.to_numeric(df[m["qtd"]], errors="coerce").fillna(0).astype(int)
    out["canal"] = (
        df[m["canal"]].astype(str).str.strip().str.upper()
        if m.get("canal") else "NAO INFORMADO"
    )
    out["vendedor"] = vendedor
    out["fonte"] = fonte
    return out[STD_COLUMNS]


def load_file(filename: str) -> pd.DataFrame:
    vendedor, m = FILES[filename]
    df = pd.read_excel(RAW_DIR / filename)
    return standardize(df, m, vendedor, filename)


def canonicalize_products(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada EAN, escolhe o nome de produto mais descritivo (mais longo)."""
    df = df.copy()
    canon = (
        df.assign(_len=df["produto"].str.len())
          .sort_values("_len", ascending=False)
          .drop_duplicates("ean")
          .set_index("ean")["produto"]
    )
    df["produto_canon"] = df["ean"].map(canon).fillna(df["produto"])
    return df


def consolidate(extra_files: list | None = None) -> pd.DataFrame:
    """Consolida planilhas enviadas via upload (e/ou lista explícita).

    Os 6 arquivos em `config.FILES` NÃO entram como dados de negócio;
    eles servem apenas como ground-truth para treinar o classificador ML.
    Sem uploads, retorna DataFrame vazio.
    """
    from pathlib import Path
    frames = []
    mappings_log = {}

    sources = list(extra_files or [])
    if not sources:
        print("  (nenhum arquivo para processar — aguardando upload)")
        empty = pd.DataFrame(columns=STD_COLUMNS + ["produto_canon", "preco_unit"])
        empty["data"] = pd.to_datetime(empty["data"])
        return empty

    from . import smart_etl  # import tardio
    for path in sources:
        path = Path(path)
        if not path.exists() or path.suffix.lower() not in {".xlsx", ".xls"}:
            continue
        try:
            df_std, mp, conf = smart_etl.process_file(path)
            frames.append(df_std)
            mappings_log[path.name] = {
                "mapping": mp,
                "confidences": {k: round(v, 3) for k, v in conf.items()},
                "linhas": int(len(df_std)),
            }
            print(f"  [ml] {path.name}: {len(df_std)} linhas (mapping inferido)")
        except Exception as e:
            print(f"  [erro-ml] {path.name}: {e}")
            mappings_log[path.name] = {"erro": str(e)}

    if not frames:
        empty = pd.DataFrame(columns=STD_COLUMNS + ["produto_canon", "preco_unit"])
        empty["data"] = pd.to_datetime(empty["data"])
        return empty

    df = pd.concat(frames, ignore_index=True)

    # limpeza final
    df = df[df["data"].notna()]
    df = df[df["valor"] > 0]

    before = len(df)
    df = df.drop_duplicates(subset=["cnpj", "data", "ean", "valor", "qtd"])
    print(f"  dedup: {before} -> {len(df)} ({before - len(df)} duplicadas removidas)")

    df = canonicalize_products(df)
    df["data"] = pd.to_datetime(df["data"]).dt.normalize()
    df["preco_unit"] = np.where(df["qtd"] > 0, df["valor"] / df["qtd"], df["valor"])

    if mappings_log:
        import json
        (PROCESSED_DIR / "ml_mappings.json").write_text(
            json.dumps(mappings_log, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return df


def main(extra_files: list | None = None):
    print("[ETL] Consolidando planilhas...")
    df = consolidate(extra_files=extra_files)
    pq = PROCESSED_DIR / "vendas.parquet"
    csv = PROCESSED_DIR / "vendas.csv"
    df.to_parquet(pq, index=False)
    df.to_csv(csv, index=False, encoding="utf-8-sig")
    if df.empty:
        print("[ETL] 0 linhas (sem uploads). Dashboard ficará no estado vazio.")
    else:
        print(f"[ETL] {len(df)} linhas | {df['data'].min().date()} -> {df['data'].max().date()}")
    print(f"[ETL] gravado em {pq.relative_to(pq.parents[2])}")
    return df


if __name__ == "__main__":
    main()
