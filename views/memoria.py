"""Memória do Agente — histórico semântico e preferências."""
from __future__ import annotations

import streamlit as st

from components.ui import fmt_br, page_header, register_plotly_theme
from rag.retriever import RAGRetriever

TPL = register_plotly_theme()

page_header(
    "Memória do Agente",
    "Histórico semântico, contexto persistente e preferências de uso",
)

retriever = RAGRetriever()

tab1, tab2, tab3 = st.tabs(["Histórico da sessão", "Busca semântica", "Preferências"])

# ── Session history ───────────────────────────────────────────────────────────
with tab1:
    history = st.session_state.get("chat_history", [])
    if not history:
        st.info("Nenhuma conversa nesta sessão. Faça perguntas na página Chat Analítico.")
    else:
        st.metric("Turnos na sessão", fmt_br(len(history)))
        st.divider()
        for i, entry in enumerate(reversed(history)):
            with st.expander(f"[{len(history) - i}] {entry['question'][:80]}", expanded=False):
                st.markdown(f"**Pergunta:** {entry['question']}")
                if entry.get("sql"):
                    st.code(entry["sql"], language="sql")
                st.markdown(f"**Resposta:** {entry['answer'][:300]}...")
                if entry.get("tables_used"):
                    st.caption(f"Tabelas: {', '.join(entry['tables_used'])}")

        if st.button("Limpar histórico da sessão", use_container_width=False):
            st.session_state.chat_history = []
            st.success("Histórico limpo.")
            st.rerun()

# ── Semantic search ───────────────────────────────────────────────────────────
with tab2:
    st.subheader("Busca no Dicionário (RAG)")
    st.caption("Pesquise campos e tabelas do SINAN usando linguagem natural")
    query = st.text_input("Buscar no dicionário...", placeholder="ex: código do município, casos confirmados")
    if query:
        with st.spinner("Buscando..."):
            context = retriever.retrieve(query, n_results=10)
        st.markdown("**Resultados:**")
        st.text(context)

    st.divider()
    if st.button("Reconstruir índice RAG", use_container_width=False):
        with st.spinner("Reconstruindo..."):
            try:
                retriever._indexer.rebuild_index()
                retriever._collection = None
                st.success("✅ Índice reconstruído com sucesso.")
            except Exception as exc:
                st.error(f"Erro: {exc}")

# ── Preferences ───────────────────────────────────────────────────────────────
with tab3:
    history = st.session_state.get("chat_history", [])
    if not history:
        st.info("Sem dados suficientes para identificar preferências.")
    else:
        from collections import Counter
        table_counts: Counter = Counter()
        for entry in history:
            for t in entry.get("tables_used", []):
                table_counts[t] += 1

        if table_counts:
            st.markdown("##### Tabelas mais consultadas")
            import pandas as pd
            import plotly.express as px
            df_prefs = pd.DataFrame(table_counts.most_common(), columns=["Tabela", "Consultas"])
            fig = px.bar(df_prefs, x="Tabela", y="Consultas", title="Uso por tabela",
                         template=TPL, color="Consultas")
            st.plotly_chart(fig, use_container_width=True)

        # Detect filter patterns
        filter_words: Counter = Counter()
        for entry in history:
            for f in entry.get("filters_applied", []):
                filter_words[f.lower()] += 1
        if filter_words:
            st.markdown("##### Filtros mais usados")
            for f, count in filter_words.most_common(5):
                st.markdown(f"- `{f}` — **{count}x**")
