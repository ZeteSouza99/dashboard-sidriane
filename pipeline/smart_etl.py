"""ETL inteligente: ingere QUALQUER xlsx usando o classificador de schema (ML).

Uso:
  python -m pipeline.smart_etl caminho/arquivo.xlsx
  python -m pipeline.smart_etl caminho/arquivo.xlsx --vendedor "Nome do distribuidor"
  python -m pipeline.smart_etl --validate    # avalia o modelo nos 6 arquivos conhecidos
  python -m pipeline.smart_etl --train       # re-treina e salva
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
import pandas as pd

from . import schema_ml
from .etl import standardize


def process_file(path: Path, vendedor: str | None = None) -> tuple[pd.DataFrame, dict, dict]:
    """Lê xlsx, infere mapping via ML e retorna (df padronizado, mapping, confidências)."""
    path = Path(path)
    df_raw = pd.read_excel(path)
    mapping, conf = schema_ml.predict_mapping(df_raw)

    # campos obrigatórios mínimos
    obrig = ["cnpj", "data", "produto", "valor", "qtd"]
    faltando = [f for f in obrig if f not in mapping]
    if faltando:
        raise ValueError(
            f"Campos obrigatórios não identificados em {path.name}: {faltando}\n"
            f"Mapping inferido: {mapping}"
        )

    vendedor = vendedor or f"Auto · {path.stem}"
    df_std = standardize(df_raw, mapping, vendedor=vendedor, fonte=path.name)
    return df_std, mapping, conf


def _print_mapping(name: str, mapping: dict, conf: dict):
    print(f"\nMapping inferido para {name}:")
    print(f"  {'campo':<10}  {'coluna':<32}  conf")
    print(f"  {'-'*10}  {'-'*32}  {'-'*5}")
    for field in schema_ml.FIELDS:
        col = mapping.get(field, "(não encontrado)")
        c = conf.get(field, 0.0)
        print(f"  {field:<10}  {str(col):<32}  {c:.2f}")


def main():
    ap = argparse.ArgumentParser(description="Ingestão inteligente de planilhas de vendas")
    ap.add_argument("path", nargs="?", help="Caminho do .xlsx a processar")
    ap.add_argument("--vendedor", help="Nome do vendedor/distribuidor (opcional)")
    ap.add_argument("--validate", action="store_true", help="Valida o classificador nos arquivos conhecidos")
    ap.add_argument("--train", action="store_true", help="Re-treina o classificador e sai")
    args = ap.parse_args()

    if args.train:
        schema_ml.train(verbose=True)
        return
    if args.validate:
        schema_ml.validate()
        return
    if not args.path:
        ap.print_help()
        sys.exit(1)

    df_std, mp, conf = process_file(args.path, vendedor=args.vendedor)
    _print_mapping(Path(args.path).name, mp, conf)
    print(f"\nDataFrame padronizado: {len(df_std)} linhas, {df_std['cnpj'].nunique()} CNPJs únicos")
    print(df_std.head(5).to_string())


if __name__ == "__main__":
    main()
