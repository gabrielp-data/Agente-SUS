"""RAG retriever — busca leve por sobreposição de termos no dicionário SINAN."""
from __future__ import annotations

from rag.indexer import RAGIndexer, normalize, tokenize
from utils.logger import get_logger

logger = get_logger("rag.retriever")

# Palavras muito comuns que não ajudam na busca
_STOPWORDS = {
    "de", "da", "do", "das", "dos", "e", "em", "no", "na", "nos", "nas",
    "o", "a", "os", "as", "um", "uma", "por", "para", "com", "que", "qual",
    "quais", "quanto", "quantos", "quantas", "sobre", "ao", "aos", "the",
}


class RAGRetriever:
    """Recupera contexto relevante do dicionário SINAN para uma pergunta."""

    def __init__(self) -> None:
        self._indexer = RAGIndexer()
        self._collection = None  # compat. com chamadas antigas

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _query_tokens(self, question: str) -> set[str]:
        return {t for t in tokenize(question) if t not in _STOPWORDS and len(t) > 1}

    def _score(self, qtokens: set[str], qnorm: str, doc: dict) -> float:
        score = 0.0
        for t in qtokens:
            if t in doc["tokens"]:
                score += 2.0           # termo exato
            elif t in doc["norm"]:
                score += 1.0           # casamento parcial (substring)
        return score

    def _ranked(self, question: str, n: int) -> list[dict]:
        qtokens = self._query_tokens(question)
        if not qtokens:
            return []
        qnorm = normalize(question)
        scored = []
        for doc in self._indexer.documents:
            s = self._score(qtokens, qnorm, doc)
            if s > 0:
                scored.append((s, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for _, doc in scored[:n]]

    # ── Public ────────────────────────────────────────────────────────────────

    def retrieve(self, question: str, n_results: int = 8) -> str:
        """Retorna um contexto formatado com os campos mais relevantes."""
        try:
            docs = self._ranked(question, n_results)
            if not docs:
                return "Nenhum contexto relevante encontrado no dicionário."

            lines = ["=== Contexto do Dicionário SINAN (RAG) ==="]
            seen_tables: set[str] = set()
            for doc in docs:
                if doc["column"] == "_table_":
                    if doc["table"] not in seen_tables:
                        lines.append(f"\n[Tabela] {doc['text']}")
                        seen_tables.add(doc["table"])
                else:
                    lines.append(f"  • {doc['text']}")
            return "\n".join(lines)
        except Exception as exc:
            logger.warning("Falha no RAG: %s — continuando sem contexto.", exc)
            return "Dicionário RAG indisponível no momento."

    def get_relevant_tables(self, question: str, n_results: int = 10) -> list[str]:
        """Lista de tabelas mais relevantes para a pergunta (sem duplicar)."""
        try:
            docs = self._ranked(question, n_results)
            tables: list[str] = []
            for doc in docs:
                t = doc.get("table", "")
                if t and t not in tables:
                    tables.append(t)
            return tables
        except Exception:
            return []
