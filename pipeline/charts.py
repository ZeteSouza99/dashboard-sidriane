"""Gráficos estáticos matplotlib salvos em web/charts/."""
from __future__ import annotations
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .config import CHARTS_DIR

PALETTE = ["#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444", "#8b5cf6", "#22c55e"]

plt.rcParams.update({
    "figure.facecolor": "#0b1220",
    "axes.facecolor": "#0b1220",
    "savefig.facecolor": "#0b1220",
    "text.color": "#e5e7eb",
    "axes.labelcolor": "#cbd5e1",
    "xtick.color": "#94a3b8",
    "ytick.color": "#94a3b8",
    "axes.edgecolor": "#1f2937",
    "axes.grid": True,
    "grid.color": "#1f2937",
    "font.size": 10,
})


def _save(fig, name):
    path = CHARTS_DIR / name
    fig.tight_layout()
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


def vendas_diarias(daily: pd.DataFrame, proj: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(daily["data"], daily["valor"], marker="o", color=PALETTE[0], label="Realizado")
    ax.fill_between(proj["data"], proj["lower"], proj["upper"], alpha=0.2, color=PALETTE[2], label="Banda ±1.5σ")
    ax.plot(proj["data"], proj["valor_proj"], "--", color=PALETTE[2], label="Projeção")
    ax.set_title("Vendas diárias e projeção", color="#f1f5f9")
    ax.set_ylabel("R$")
    ax.legend()
    _save(fig, "vendas_diarias.png")


def por_vendedor(g: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.barh(g["vendedor"], g["valor"], color=PALETTE[1])
    ax.invert_yaxis()
    ax.set_title("Vendas por vendedor / distribuidor", color="#f1f5f9")
    ax.set_xlabel("R$")
    _save(fig, "por_vendedor.png")


def por_canal(g: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.pie(g["valor"], labels=g["canal"], autopct="%1.1f%%", colors=PALETTE, startangle=90,
           wedgeprops=dict(edgecolor="#0b1220", linewidth=2))
    ax.set_title("Mix de vendas por canal", color="#f1f5f9")
    _save(fig, "por_canal.png")


def top_prods(g: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 5))
    rotulo = g["produto_canon"].str.slice(0, 55)
    ax.barh(rotulo, g["valor"], color=PALETTE[3])
    ax.invert_yaxis()
    ax.set_title("Top 10 produtos por valor", color="#f1f5f9")
    ax.set_xlabel("R$")
    _save(fig, "top_produtos.png")


def gerar_todos(df, daily, proj, vended, canal, top):
    vendas_diarias(daily, proj)
    por_vendedor(vended)
    por_canal(canal)
    top_prods(top)
