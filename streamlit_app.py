"""Wrapper Streamlit para hospedar o dashboard no Streamlit Community Cloud.

O dashboard rico (HTML + Tailwind + Chart.js em web/) é embedado dentro de um
iframe via st.components.v1.html, com o data.json injetado em window.DASHBOARD_DATA.

O Streamlit cuida do upload e dispara o pipeline (pipeline.etl + pipeline.analytics).
"""
from __future__ import annotations
import json
import shutil
import tempfile
from pathlib import Path

import streamlit as st

from pipeline import etl, analytics
from pipeline.config import WEB_DIR, PROCESSED_DIR

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

st.set_page_config(
    page_title="Dashboard Sidriane",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# CSS leve para esconder o chrome do Streamlit e dar mais espaço ao iframe
st.markdown(
    """
    <style>
      header[data-testid="stHeader"] { background: transparent; }
      .block-container { padding-top: 1rem; padding-bottom: 0; max-width: 100% !important; }
      #MainMenu, footer { visibility: hidden; }
      .stApp { background: #0b1220; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------- session state ----------------------
if "upload_dir" not in st.session_state:
    # diretório temporário por sessão para isolar uploads entre usuários
    st.session_state.upload_dir = Path(tempfile.mkdtemp(prefix="dashsidri_"))
    st.session_state.uploads = []

UPLOAD_DIR: Path = st.session_state.upload_dir


@st.cache_data(show_spinner=False)
def _read_static(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def run_pipeline(extras: list[Path]) -> dict:
    """Roda ETL + Analytics e devolve o data.json como dict."""
    etl.main(extra_files=extras)
    analytics.main()
    data_path = WEB_DIR / "data.json"
    return json.loads(data_path.read_text(encoding="utf-8"))


def render_dashboard(data: dict, height: int = 4200):
    """Embeda o dashboard HTML com o data.json injetado inline."""
    html = _read_static("index.html")
    css = _read_static("styles.css")
    js = _read_static("app.js")

    # remove tags externas e injeta tudo inline + dados
    html = html.replace(
        '<link rel="stylesheet" href="styles.css">',
        f"<style>{css}</style>",
    )
    html = html.replace(
        '<script src="app.js"></script>',
        f"<script>window.DASHBOARD_DATA = {json.dumps(data, ensure_ascii=False)};</script>"
        f"<script>{js}</script>",
    )
    st.iframe(srcdoc=html, height=height, scrolling=True)


# ---------------------- UI ----------------------
st.title("📊 Dashboard Sidriane — Vendas Pharma")
st.caption(
    "Suba 1+ planilhas .xlsx de vendas. O ML detecta o schema automaticamente "
    "e gera todos os indicadores. Os arquivos ficam apenas em memória da sua sessão."
)

with st.expander("📥 Importar planilhas (.xlsx)", expanded=not st.session_state.uploads):
    files = st.file_uploader(
        "Arraste ou clique para selecionar",
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if files and st.button("🚀 Processar arquivos", type="primary", use_container_width=True):
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            saved = []
            for f in files:
                dest = UPLOAD_DIR / f.name
                dest.write_bytes(f.getbuffer())
                saved.append(dest)
            st.session_state.uploads = saved
            with st.spinner("ML classificando schema e calculando KPIs..."):
                try:
                    data = run_pipeline(saved)
                    st.session_state.data = data
                    st.success(f"✅ {len(saved)} arquivo(s) processado(s).")
                except Exception as e:
                    st.error(f"Falha no pipeline: {e}")
    with col_b:
        if st.session_state.uploads and st.button("🗑️ Limpar tudo", use_container_width=True):
            shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
            UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
            st.session_state.uploads = []
            st.session_state.pop("data", None)
            try:
                run_pipeline([])  # gera estado vazio
            except Exception:
                pass
            st.rerun()

    if st.session_state.uploads:
        st.caption("Arquivos ativos: " + ", ".join(p.name for p in st.session_state.uploads))

# ---------------------- Dashboard ----------------------
data = st.session_state.get("data")
if data is None:
    # primeira carga: garante estado vazio
    try:
        data = run_pipeline([])
    except Exception as e:
        st.warning(f"Pipeline ainda não inicializado: {e}")
        data = {"empty": True, "meta": {"gerado_em": "", "notas": []}}

render_dashboard(data)
