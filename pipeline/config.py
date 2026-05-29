"""Configurações centrais: caminhos e mapeamento de colunas por arquivo."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT  # planilhas estão na raiz do projeto
PROCESSED_DIR = ROOT / "data" / "processed"
WEB_DIR = ROOT / "web"
CHARTS_DIR = WEB_DIR / "charts"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

# (vendedor/distribuidor, mapeamento de colunas brutas -> nomes padronizados)
FILES = {
    "acre.xlsx": (
        "Distribuidor Acre",
        {
            "cliente": "RAZAOSOCIAL",
            "cnpj": "CNPJ",
            "uf": "UF",
            "data": "DATAVENDA",
            "ean": "EAN",
            "produto": "descrição",
            "valor": "VALOR_VENDA",
            "qtd": "QTDE_VENDA",
            "canal": "painel",
        },
    ),
    "MTF PA.xlsx": (
        "MTF Pará",
        {
            "cliente": "Cliente",
            "cnpj": "CNPJ CPF",
            "uf": "Estado",
            "data": "Data Dia",
            "ean": "Cód Barras Compra",
            "produto": "Produto",
            "valor": "VALOR",
            "qtd": "UN ",
            "canal": "PAINEL",
        },
    ),
    "TAPAJÓS AM.xlsx": (
        "Tapajós AM",
        {
            "cliente": "Cliente",
            "cnpj": "CNPJ_CLIENTE",
            "uf": "UF",
            "data": "Data",
            "ean": "EAN",
            "produto": "Produto",
            "valor": "Valor Total Nota",
            "qtd": "Qtd",
            "canal": "painel",
        },
    ),
    "TAPAJÓS RO.xlsx": (
        "Tapajós RO",
        {
            "cliente": None,
            "cnpj": "CNPJ CLIENTE",
            "uf": "UF",
            "data": "DATA VENDA",
            "ean": None,
            "produto": "PRODUTO",
            "valor": "VL TOTAL VENDA",
            "qtd": "QTD TOTAL VENDA",
            "canal": "PAINEL ",
        },
    ),
    "TAPAJÓS RR.xlsx": (
        "Tapajós RR",
        {
            "cliente": "Cliente",
            "cnpj": "CNPJ_CLIENTE",
            "uf": "UF",
            "data": "Data",
            "ean": "EAN",
            "produto": "Produto",
            "valor": "Valor Total Nota",
            "qtd": "Qtd",
            "canal": "PAINEL ",
        },
    ),
    "total AM.xlsx": (
        "Equipe AM",
        {
            "cliente": "Cliente",
            "cnpj": "CNPJ CPF",
            "uf": "Estado",
            "data": "Data Dia",
            "ean": "Cód Barras Compra",
            "produto": "Produto",
            "valor": "VALOR",
            "qtd": "UN ",
            "canal": "PAINEL",
        },
    ),
}

STD_COLUMNS = ["cliente", "cnpj", "uf", "data", "ean", "produto", "valor", "qtd", "canal", "vendedor", "fonte"]
