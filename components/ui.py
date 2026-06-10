"""Shared UI helpers — formatação BR, tema Plotly e cabeçalhos profissionais."""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

# Paleta de marca (consistente em toda a plataforma)
BRAND_COLORS = ["#4f8ef7", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#06b6d4"]


def fmt_br(n: int | float | None) -> str:
    """Formata número no padrão brasileiro: 1234567 -> '1.234.567'."""
    if n is None:
        return "—"
    try:
        return f"{float(n):,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return str(n)


def fmt_br_decimal(n: float | None, casas: int = 1) -> str:
    """Formata decimal no padrão BR: 1234.5 -> '1.234,5'."""
    if n is None:
        return "—"
    try:
        s = f"{float(n):,.{casas}f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return str(n)


def page_header(title: str, subtitle: str = "") -> None:
    """Cabeçalho de página padronizado — wordmark com marca, sem emoji."""
    sub_html = (
        f'<div style="opacity:.6;font-size:.92rem;margin-top:.3rem;'
        f'margin-left:1.35rem;max-width:680px;">{subtitle}</div>'
        if subtitle else ""
    )
    st.markdown(
        f"""
        <div style="padding:.25rem 0 1rem;">
          <div style="display:flex;align-items:center;gap:.65rem;">
            <span style="width:11px;height:11px;border-radius:3px;
                  background:linear-gradient(135deg,#4f8ef7,#22c55e);
                  display:inline-block;flex-shrink:0;"></span>
            <span style="font-size:1.6rem;font-weight:700;letter-spacing:-.4px;">{title}</span>
          </div>
          {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def section(title: str) -> None:
    """Subtítulo de seção discreto e consistente."""
    st.markdown(
        f'<div style="font-size:.78rem;text-transform:uppercase;letter-spacing:1px;'
        f'font-weight:700;opacity:.55;margin:.5rem 0 .25rem;">{title}</div>',
        unsafe_allow_html=True,
    )


def register_plotly_theme() -> str:
    """
    Registra e ativa um template Plotly ('sinan') alinhado ao tema atual.
    Retorna o nome do template para uso explícito nos gráficos.
    """
    theme = st.session_state.get("theme", "dark")
    if theme == "dark":
        font_color = "#e8eaf0"
        grid = "rgba(255,255,255,.07)"
    else:
        font_color = "#334155"
        grid = "rgba(0,0,0,.08)"

    pio.templates["sinan"] = go.layout.Template(
        layout=dict(
            font=dict(family="Inter, sans-serif", color=font_color, size=13),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=BRAND_COLORS,
            xaxis=dict(gridcolor=grid, zerolinecolor=grid, linecolor=grid),
            yaxis=dict(gridcolor=grid, zerolinecolor=grid, linecolor=grid),
            title=dict(font=dict(size=15, color=font_color), x=0.01, xanchor="left"),
            legend=dict(bgcolor="rgba(0,0,0,0)", borderwidth=0),
            margin=dict(l=12, r=12, t=48, b=12),
            hoverlabel=dict(font=dict(family="Inter, sans-serif")),
        )
    )
    pio.templates.default = "sinan"
    return "sinan"
