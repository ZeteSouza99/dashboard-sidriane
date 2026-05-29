"""Pipeline equivalente em Apache Spark (PySpark).

Executa as MESMAS agregações principais do pandas, mas via Spark SQL.
Se o ambiente não tiver Java/Spark configurado, falha de forma controlada
e o pipeline principal (pandas) continua valendo como fonte de verdade.

Saída: data/processed/spark_*.csv
"""
from __future__ import annotations
import sys
from .config import PROCESSED_DIR


def run():
    try:
        from pyspark.sql import SparkSession, functions as F
    except Exception as e:
        print(f"[Spark] pyspark indisponível: {e}")
        return False

    try:
        spark = (
            SparkSession.builder
            .appName("DashboardSidriane")
            .master("local[*]")
            .config("spark.sql.shuffle.partitions", "4")
            .config("spark.ui.showConsoleProgress", "false")
            .getOrCreate()
        )
        spark.sparkContext.setLogLevel("ERROR")
    except Exception as e:
        print(f"[Spark] Falha ao iniciar SparkSession (provável Java ausente): {e}")
        return False

    try:
        path = str(PROCESSED_DIR / "vendas.parquet")
        df = spark.read.parquet(path)
        print(f"[Spark] {df.count()} linhas carregadas")

        by_vend = (
            df.groupBy("vendedor")
              .agg(F.sum("valor").alias("valor"),
                   F.sum("qtd").alias("qtd"),
                   F.countDistinct("cnpj").alias("clientes"))
              .orderBy(F.desc("valor"))
        )
        by_canal = df.groupBy("canal").agg(F.sum("valor").alias("valor"), F.sum("qtd").alias("qtd"))
        by_uf = df.groupBy("uf").agg(F.sum("valor").alias("valor"), F.sum("qtd").alias("qtd"))
        daily = df.groupBy("data").agg(F.sum("valor").alias("valor"), F.sum("qtd").alias("qtd")).orderBy("data")

        out = PROCESSED_DIR
        for name, frame in [
            ("spark_by_vendedor", by_vend),
            ("spark_by_canal", by_canal),
            ("spark_by_uf", by_uf),
            ("spark_daily", daily),
        ]:
            frame.toPandas().to_csv(out / f"{name}.csv", index=False, encoding="utf-8-sig")
            print(f"[Spark] {name}.csv")

        spark.stop()
        return True
    except Exception as e:
        print(f"[Spark] erro durante execução: {e}")
        try: spark.stop()
        except Exception: pass
        return False


if __name__ == "__main__":
    sys.exit(0 if run() else 1)
