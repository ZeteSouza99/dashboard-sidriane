"""Teste de generalização: pega um xlsx conhecido, EMBARALHA a ordem das colunas
e RENOMEIA os headers para nomes não-vistos, depois checa se o ML mapeia certo.
"""
from __future__ import annotations
import random
import pandas as pd
from pathlib import Path

from pipeline.config import RAW_DIR, FILES
from pipeline import schema_ml, smart_etl


# Renomeações que NÃO aparecem em nenhum arquivo de treino
RENAME_BANK = {
    "cliente": ["Loja",            "Estabelecimento", "Nome do PDV"],
    "cnpj":    ["Inscricao",       "DocFiscal",       "ID Fiscal"],
    "uf":      ["Sigla",           "Regiao UF",       "ST"],
    "data":    ["Competencia",     "Emissao NF",      "Dt Movto"],
    "ean":     ["GTIN",            "SKU Code",        "Cod Item"],
    "produto": ["Mercadoria",      "Item Descricao",  "Descricao SKU"],
    "valor":   ["Receita",         "Faturado",        "Vlr Bruto"],
    "qtd":     ["Volume",          "Pecas",           "Qtd Itens"],
    "canal":   ["Tipo de Cliente", "Segmento PDV",    "Modalidade"],
}


def stress_test(filename: str = "MTF PA.xlsx", seed: int = 7):
    rng = random.Random(seed)
    src = RAW_DIR / filename
    df = pd.read_excel(src)

    _, gt_map = FILES[filename]
    inv = {v: k for k, v in gt_map.items() if v}

    # renomeia headers para nomes inéditos
    new_names = {}
    for col in df.columns:
        field = inv.get(col)
        if field and field in RENAME_BANK:
            new_names[col] = rng.choice(RENAME_BANK[field])
    df = df.rename(columns=new_names)

    # embaralha ordem das colunas
    cols = list(df.columns)
    rng.shuffle(cols)
    df = df[cols]

    # salva para inspeção
    out = RAW_DIR / "_stress_test.xlsx"
    df.to_excel(out, index=False)

    print(f"Arquivo base:      {filename}")
    print(f"Headers originais: {list(gt_map.values())}")
    print(f"Headers renomeados/embaralhados:")
    for c in df.columns:
        print(f"  - {c}")

    mapping, conf = schema_ml.predict_mapping(df)

    print("\nMapping inferido vs esperado:")
    print(f"  {'campo':<10}  {'previsto':<22}  {'esperado (renomeado)':<26}  conf  status")
    print(f"  {'-'*10}  {'-'*22}  {'-'*26}  {'-'*4}  {'-'*6}")
    ok = total = 0
    for field, orig_col in gt_map.items():
        if not orig_col: continue
        expected = new_names.get(orig_col, orig_col)
        predicted = mapping.get(field)
        total += 1
        match = predicted == expected
        ok += int(match)
        print(f"  {field:<10}  {str(predicted):<22}  {str(expected):<26}  {conf.get(field,0):.2f}  {'OK' if match else 'MISS'}")
    print(f"\nAcurácia em planilha NUNCA VISTA: {ok}/{total} = {ok/total:.0%}")

    # roda standardize completo
    df_std, mp, conf2 = smart_etl.process_file(out, vendedor="Teste Generalização")
    print(f"\nDataFrame padronizado: {len(df_std)} linhas | {df_std['cnpj'].nunique()} CNPJs únicos")
    print(df_std.head(3).to_string())

    out.unlink(missing_ok=True)


if __name__ == "__main__":
    stress_test()
