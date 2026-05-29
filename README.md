# Dashboard Sidriane

Pipeline de Ciência de Dados + Dashboard Web para vendas da linha **PRINCIPIA** nos distribuidores Norte/Centro-Oeste.

## Stack
- **Pandas / NumPy** — ETL e agregações
- **scikit-learn** — projeção de vendas (LinearRegression) e segmentação de clientes (KMeans)
- **Matplotlib** — gráficos estáticos
- **Apache Spark (PySpark)** — pipeline paralelo equivalente (opcional, requer Java)
- **HTML + Tailwind (CDN) + Chart.js** — dashboard responsivo

## Estrutura
```
pipeline/   código Python (ETL, analytics, spark, run_all)
data/raw/   planilhas xlsx originais
data/processed/  saídas consolidadas (parquet/csv)
web/        dashboard (index.html, app.js, data.json, charts/)
```

## Como executar
```powershell
# 1. Instalar dependências
pip install -r requirements.txt

# 2. Rodar pipeline completo (ETL + analytics + Spark opcional)
python -m pipeline.run_all

# 3. Servir o dashboard
cd web
python -m http.server 8000
# abrir http://localhost:8000
```

Atalho: `.\run.ps1` faz os passos 2 e 3.

## Observações sobre os dados
- **Vendedor** é derivado da origem do arquivo (cada planilha = um distribuidor regional). Os dados brutos não trazem nome de vendedor.
- **Estoque** não existe nos arquivos: é **simulado** a partir do histórico de vendas (cobertura de 60 dias). Está marcado como `SIMULADO` na UI.
- Datas em formato serial Excel (em `acre.xlsx` e `TAPAJÓS RR.xlsx`) são convertidas automaticamente.
- Deduplicação entre `total AM` e `TAPAJÓS AM` por (CNPJ, data, EAN, valor).
