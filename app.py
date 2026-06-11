"""SINAN Analytics — roteador principal (st.navigation)."""
from __future__ import annotations

import streamlit as st

from components.sidebar import render_sidebar
from components.theme import apply_theme

st.set_page_config(
    page_title="SINAN Analytics",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "About": "**SINAN Analytics** — Plataforma de análise da base SINAN/SUS "
                 "com IA generativa (AWS Bedrock), geração de SQL auditável e RAG.",
    },
)

if "theme" not in st.session_state:
    st.session_state.theme = "dark"

apply_theme()

# ── Navegação (ordem pensada: conteúdo primeiro, administração depois) ────────
inicio = st.Page("views/inicio.py", title="Início", icon=":material/home:", default=True)
chat = st.Page("views/chat.py", title="Chat Analítico", icon=":material/forum:")
painel = st.Page("views/painel.py", title="Painel Epidemiológico", icon=":material/monitoring:")
dicionario = st.Page("views/dicionario.py", title="Dicionário de Dados", icon=":material/menu_book:")
exploracao = st.Page("views/exploracao.py", title="Exploração", icon=":material/table_view:")
monitoramento = st.Page("views/monitoramento.py", title="Monitoramento", icon=":material/insights:")
memoria = st.Page("views/memoria.py", title="Memória do Agente", icon=":material/history:")
configuracoes = st.Page("views/configuracoes.py", title="Configurações", icon=":material/settings:")

nav = st.navigation({
    "": [inicio],
    "Análise": [chat, painel, dicionario, exploracao],
    "Sistema": [monitoramento, memoria, configuracoes],
})

render_sidebar()
nav.run()
