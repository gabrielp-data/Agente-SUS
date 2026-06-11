"""Shared sidebar component."""
from __future__ import annotations

import streamlit as st

from components.theme import render_theme_toggle


def render_sidebar() -> None:
    """Render the common sidebar elements (logo, nav info, theme toggle)."""
    with st.sidebar:
        render_theme_toggle()
        st.divider()

        _dot = (
            "display:inline-block;width:8px;height:8px;border-radius:50%;"
            "margin-right:9px;vertical-align:middle;"
        )
        st.markdown(
            f"""
            <div style='font-size:.7rem;text-transform:uppercase;letter-spacing:1px;
                  font-weight:700;opacity:.5;margin:.2rem 0 .55rem;'>Agravos disponíveis</div>
            <div style='font-size:13px; line-height:2.1'>
              <span style='{_dot}background:#ef4444;'></span>Dengue <span style='opacity:.5'>(anual e mensal)</span><br>
              <span style='{_dot}background:#a855f7;'></span>Botulismo <span style='opacity:.5'>(mensal)</span><br>
              <span style='{_dot}background:#22c55e;'></span>Doença de Chagas <span style='opacity:.5'>(mensal)</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown(
            "<div style='font-size:.7rem;text-transform:uppercase;letter-spacing:1px;"
            "font-weight:700;opacity:.5;margin:.2rem 0 .55rem;'>Exemplos de perguntas</div>",
            unsafe_allow_html=True,
        )
        examples = [
            "Quantos casos de dengue em Brasília em 2023?",
            "Qual UF teve mais óbitos por dengue?",
            "Tendência mensal de dengue no DF em 2024",
            "Compare dengue entre SP e RJ",
        ]
        for ex in examples:
            if st.button(f"→ {ex}", key=f"ex_{ex[:20]}", use_container_width=True):
                st.session_state["suggested_question"] = ex
                st.switch_page("pages/1_Chat.py")
