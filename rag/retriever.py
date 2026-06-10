"""RAG retriever — queries ChromaDB with a natural language question."""
from __future__ import annotations

from rag.indexer import RAGIndexer
from utils.logger import get_logger

logger = get_logger("rag.retriever")


class RAGRetriever:
    """Retrieve relevant SINAN dictionary context for a given user question."""

    def __init__(self) -> None:
        self._indexer = RAGIndexer()
        self._collection = None

    def _ensure_collection(self):
        if self._collection is None:
            self._collection = self._indexer.get_or_create_collection()
        return self._collection

    def retrieve(self, question: str, n_results: int = 8) -> str:
        """
        Query ChromaDB and return a formatted context string.

        Args:
            question:  User's natural language question
            n_results: Number of top documents to return

        Returns:
            A formatted string ready to be injected into a prompt.
        """
        try:
            collection = self._ensure_collection()
            results = collection.query(
                query_texts=[question],
                n_results=min(n_results, collection.count() or 1),
            )

            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]

            if not docs:
                return "Nenhum contexto relevante encontrado no dicionário."

            lines = ["=== Contexto do Dicionário SINAN (RAG) ==="]
            seen_tables: set[str] = set()

            for doc, meta in zip(docs, metas):
                table = meta.get("table", "")
                if meta.get("column") == "_table_" and table not in seen_tables:
                    lines.append(f"\n[Tabela] {doc}")
                    seen_tables.add(table)
                elif meta.get("column") != "_table_":
                    lines.append(f"  • {doc}")

            context = "\n".join(lines)
            logger.debug("RAG: %d documentos recuperados para a pergunta.", len(docs))
            return context

        except Exception as exc:
            logger.warning("Falha no RAG: %s — continuando sem contexto.", exc)
            return "Dicionário RAG indisponível no momento."

    def get_relevant_tables(self, question: str, n_results: int = 10) -> list[str]:
        """Return a deduplicated list of table names most relevant to the question."""
        try:
            collection = self._ensure_collection()
            results = collection.query(
                query_texts=[question],
                n_results=min(n_results, collection.count() or 1),
            )
            metas = results.get("metadatas", [[]])[0]
            tables: list[str] = []
            seen: set[str] = set()
            for meta in metas:
                t = meta.get("table", "")
                if t and t not in seen:
                    tables.append(t)
                    seen.add(t)
            return tables
        except Exception:
            return []
