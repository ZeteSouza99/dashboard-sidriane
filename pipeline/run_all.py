"""Orquestrador: ETL -> Analytics -> Spark (opcional)."""
from pathlib import Path
from . import etl, analytics, spark_jobs

UPLOAD_DIR = Path(__file__).resolve().parent.parent / "uploads"


def main():
    extras = sorted(UPLOAD_DIR.glob("*.xlsx")) if UPLOAD_DIR.exists() else None
    etl.main(extra_files=extras)
    analytics.main()
    ok = spark_jobs.run()
    print("\n[run_all] Concluído.")
    print(f"  - pandas/sklearn pipeline: OK")
    print(f"  - spark pipeline: {'OK' if ok else 'SKIP (Java/Spark indisponível)'}")
    print("  - abra web/index.html (sirva via `python -m http.server` na pasta web/)")


if __name__ == "__main__":
    main()
