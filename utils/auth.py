"""Proteção das páginas administrativas com senha (ADMIN_PASSWORD).

Em produção (Streamlit Cloud), defina ADMIN_PASSWORD nos Secrets.
Sem ADMIN_PASSWORD configurada (dev local), o acesso é liberado.
"""
from __future__ import annotations

import hmac
import os

import streamlit as st


def _admin_password() -> str | None:
    """Lê a senha de admin do ambiente ou dos secrets do Streamlit."""
    pw = os.getenv("ADMIN_PASSWORD")
    if pw:
        return pw
    try:
        return st.secrets.get("ADMIN_PASSWORD")  # type: ignore[no-any-return]
    except Exception:
        return None


def admin_unlocked() -> bool:
    """True se não há senha configurada (dev) ou se a sessão já autenticou."""
    pw = _admin_password()
    if not pw:
        return True
    return bool(st.session_state.get("is_admin"))


def require_admin() -> bool:
    """
    Bloqueia a página até autenticar. Retorna True quando liberado.

    Uso no topo da página:
        if not require_admin():
            st.stop()
    """
    if admin_unlocked():
        return True

    st.warning("Esta página é restrita ao administrador.", icon="🔒")
    with st.form("admin_gate"):
        entered = st.text_input("Senha de administrador", type="password")
        ok = st.form_submit_button("Entrar", use_container_width=True)

    if ok:
        expected = _admin_password() or ""
        if hmac.compare_digest(entered, expected):
            st.session_state.is_admin = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False
