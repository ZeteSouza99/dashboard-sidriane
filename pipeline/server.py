"""Servidor Flask: serve o dashboard e expõe API de upload de planilhas.

Endpoints:
  GET  /                 -> dashboard
  GET  /<path>           -> arquivos estáticos (data.json, app.js, ...)
  POST /api/upload       -> multipart com 1+ arquivos .xlsx
  POST /api/reset        -> remove uploads e reprocessa só os arquivos originais
  GET  /api/state        -> lista de uploads ativos + ml_mappings
"""
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

from .config import WEB_DIR, PROCESSED_DIR
from . import etl, analytics

ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = ROOT / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)
ALLOWED = {".xlsx", ".xls"}

app = Flask(__name__, static_folder=str(WEB_DIR), static_url_path="")
CORS(app)


def _safe_name(name: str) -> str:
    name = re.sub(r"[^\w\.\-]+", "_", name, flags=re.UNICODE).strip("._-")
    return name or "upload.xlsx"


def _run_pipeline():
    extras = sorted(UPLOAD_DIR.glob("*.xlsx"))
    etl.main(extra_files=extras)
    analytics.main()
    # ml_mappings.json (gerado pelo etl quando há extras)
    mp_path = PROCESSED_DIR / "ml_mappings.json"
    mappings = json.loads(mp_path.read_text(encoding="utf-8")) if mp_path.exists() else {}
    return mappings


# ----------------------------- static -----------------------------

@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    target = WEB_DIR / path
    if not target.exists():
        abort(404)
    return send_from_directory(WEB_DIR, path)


# ----------------------------- api -----------------------------

@app.post("/api/upload")
def upload():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "erro": "Nenhum arquivo recebido"}), 400

    saved, rejected = [], []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ALLOWED:
            rejected.append({"nome": f.filename, "motivo": "extensão inválida"})
            continue
        name = _safe_name(f.filename)
        dest = UPLOAD_DIR / name
        f.save(dest)
        saved.append(name)

    if not saved:
        return jsonify({"ok": False, "erro": "Nenhum xlsx válido", "rejeitados": rejected}), 400

    try:
        mappings = _run_pipeline()
    except Exception as e:
        return jsonify({"ok": False, "erro": f"Falha no pipeline: {e}", "salvos": saved}), 500

    return jsonify({
        "ok": True,
        "salvos": saved,
        "rejeitados": rejected,
        "mappings": {k: v for k, v in mappings.items() if k in saved},
        "uploads_ativos": [p.name for p in sorted(UPLOAD_DIR.glob("*.xlsx"))],
    })


@app.post("/api/reset")
def reset():
    for p in UPLOAD_DIR.glob("*.xlsx"):
        p.unlink()
    try:
        _run_pipeline()
    except Exception as e:
        return jsonify({"ok": False, "erro": str(e)}), 500
    return jsonify({"ok": True, "uploads_ativos": []})


@app.get("/api/state")
def state():
    mp_path = PROCESSED_DIR / "ml_mappings.json"
    mappings = json.loads(mp_path.read_text(encoding="utf-8")) if mp_path.exists() else {}
    return jsonify({
        "uploads_ativos": [p.name for p in sorted(UPLOAD_DIR.glob("*.xlsx"))],
        "mappings": mappings,
    })


def main():
    # garante que data.json existe ao iniciar
    if not (WEB_DIR / "data.json").exists():
        _run_pipeline()
    print("Dashboard:  http://localhost:8000")
    print("API upload: POST http://localhost:8000/api/upload  (multipart files=...)")
    app.run(host="0.0.0.0", port=8000, debug=False)


if __name__ == "__main__":
    main()
