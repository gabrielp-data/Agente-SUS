"""Testes da busca leve no dicionário SINAN (RAG em memória)."""
from rag.retriever import RAGRetriever


def _retriever() -> RAGRetriever:
    return RAGRetriever()


def test_encontra_codigo_municipio():
    docs = _retriever()._ranked("codigo do municipio", 3)
    assert docs, "busca não retornou nada"
    assert all(d["column"] == "codigo_municipio" for d in docs)


def test_encontra_colunas_de_obito():
    docs = _retriever()._ranked("obitos por dengue", 3)
    assert any("obito" in d["column"] for d in docs)


def test_tabelas_relevantes_para_dengue_anual():
    tabelas = _retriever().get_relevant_tables("casos de dengue por ano", 4)
    assert "sus_sinan_dengue_anual" in tabelas


def test_busca_sem_termos_uteis_retorna_vazio():
    assert _retriever()._ranked("de a o", 5) == []


def test_retrieve_formata_contexto():
    ctx = _retriever().retrieve("casos por mes", n_results=5)
    assert "Contexto do Dicionário SINAN" in ctx
