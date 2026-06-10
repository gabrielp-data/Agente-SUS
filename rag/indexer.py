"""Index the SINAN data dictionary into ChromaDB for RAG retrieval."""
from __future__ import annotations

import json
import os
from pathlib import Path

from utils.logger import get_logger

logger = get_logger("rag.indexer")

CHROMA_DIR = "data/chroma_db"
COLLECTION_NAME = "sinan_dictionary"
DICT_PATH = "data/dicionario_sinan.json"


class RAGIndexer:
    """Builds and maintains the ChromaDB vector index for the SINAN dictionary."""

    def __init__(self) -> None:
        self._client = None
        self._collection = None

    def _get_client(self):
        if self._client is None:
            try:
                import chromadb

                os.makedirs(CHROMA_DIR, exist_ok=True)
                self._client = chromadb.PersistentClient(path=CHROMA_DIR)
            except ImportError as exc:
                raise RuntimeError(
                    "ChromaDB não instalado. Execute: pip install chromadb"
                ) from exc
        return self._client

    def get_or_create_collection(self):
        """Return existing collection or build a fresh one from the dictionary."""
        client = self._get_client()
        existing = [c.name for c in client.list_collections()]

        if COLLECTION_NAME in existing:
            self._collection = client.get_collection(COLLECTION_NAME)
            logger.info("Coleção RAG carregada (%d docs).", self._collection.count())
        else:
            self._collection = client.create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._index_dictionary()

        return self._collection

    def rebuild_index(self) -> None:
        """Delete and recreate the collection."""
        client = self._get_client()
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = client.create_collection(
            COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
        )
        self._index_dictionary()
        logger.info("Índice RAG reconstruído.")

    # ── Private ───────────────────────────────────────────────────────────────

    def _index_dictionary(self) -> None:
        """Load dicionario_sinan.json and insert one document per column."""
        if not os.path.exists(DICT_PATH):
            logger.warning("Dicionário não encontrado em %s — RAG vazio.", DICT_PATH)
            return

        with open(DICT_PATH, encoding="utf-8") as f:
            data = json.load(f)

        documents, metadatas, ids = [], [], []

        for table_name, table_info in data["tables"].items():
            table_desc = table_info.get("description", "")
            disease = table_info.get("disease", "")
            granularity = table_info.get("granularity", "")

            # One document per column
            for col in table_info.get("columns", []):
                doc_text = (
                    f"Tabela: {table_name} | "
                    f"Doença: {disease} | "
                    f"Granularidade: {granularity} | "
                    f"Coluna: {col['name']} | "
                    f"Tipo: {col['type']} | "
                    f"Descrição: {col['description']}"
                )
                if col.get("example"):
                    doc_text += f" | Exemplo: {col['example']}"

                doc_id = f"{table_name}__{col['name']}"
                documents.append(doc_text)
                metadatas.append(
                    {
                        "table": table_name,
                        "column": col["name"],
                        "type": col["type"],
                        "disease": disease,
                        "granularity": granularity,
                    }
                )
                ids.append(doc_id)

            # Also index the table itself as a document
            table_doc = (
                f"Tabela: {table_name} | "
                f"Doença: {disease} | "
                f"Granularidade: {granularity} | "
                f"Descrição: {table_desc}"
            )
            documents.append(table_doc)
            metadatas.append(
                {"table": table_name, "column": "_table_", "disease": disease, "granularity": granularity, "type": "table"}
            )
            ids.append(f"{table_name}__TABLE")

        # Batch upsert
        batch_size = 50
        for i in range(0, len(documents), batch_size):
            self._collection.add(
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )

        logger.info("RAG: %d documentos indexados em %d tabelas.", len(documents), len(data["tables"]))
