"""Index the SINAN data dictionary into ChromaDB for RAG retrieval."""
from __future__ import annotations

# ChromaDB exige sqlite3 >= 3.35. No Streamlit Cloud o sqlite do sistema é antigo;
# substituímos pelo pysqlite3 (pacote pysqlite3-binary) quando disponível.
# Em Windows/local mantém o sqlite padrão (ImportError ignorado).
try:  # pragma: no cover
    __import__("pysqlite3")
    import sys as _sys
    _sys.modules["sqlite3"] = _sys.modules.pop("pysqlite3")
except Exception:
    pass

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
        """Load dicionario_sinan.json and insert one document per column.

        Suporta o JSON em português ("tabelas"/"colunas"/"nome"/"tipo"/"descricao")
        com fallback para as chaves em inglês.
        """
        if not os.path.exists(DICT_PATH):
            logger.warning("Dicionário não encontrado em %s — RAG vazio.", DICT_PATH)
            return

        with open(DICT_PATH, encoding="utf-8") as f:
            data = json.load(f)

        tabelas = data.get("tabelas") or data.get("tables") or {}
        documents, metadatas, ids = [], [], []

        for table_name, table_info in tabelas.items():
            table_desc  = table_info.get("descricao")    or table_info.get("description", "")
            disease     = table_info.get("doenca")       or table_info.get("disease", "")
            granularity = table_info.get("granularidade") or table_info.get("granularity", "")
            colunas     = table_info.get("colunas")      or table_info.get("columns") or []

            for col in colunas:
                nome    = col.get("nome")      or col.get("name", "")
                tipo    = col.get("tipo")      or col.get("type", "")
                desc    = col.get("descricao") or col.get("description", "")
                exemplo = col.get("exemplo")   or col.get("example", "")

                doc_text = (
                    f"Tabela: {table_name} | "
                    f"Doença: {disease} | "
                    f"Granularidade: {granularity} | "
                    f"Coluna: {nome} | "
                    f"Tipo: {tipo} | "
                    f"Descrição: {desc}"
                )
                if exemplo:
                    doc_text += f" | Exemplo: {exemplo}"

                documents.append(doc_text)
                metadatas.append({
                    "table": table_name,
                    "column": nome,
                    "type": str(tipo),
                    "disease": disease,
                    "granularity": granularity,
                })
                ids.append(f"{table_name}__{nome}")

            # Documento da tabela em si
            table_doc = (
                f"Tabela: {table_name} | "
                f"Doença: {disease} | "
                f"Granularidade: {granularity} | "
                f"Descrição: {table_desc}"
            )
            documents.append(table_doc)
            metadatas.append(
                {"table": table_name, "column": "_table_", "disease": disease,
                 "granularity": granularity, "type": "table"}
            )
            ids.append(f"{table_name}__TABLE")

        if not documents:
            logger.warning("Dicionário sem colunas reconhecidas — RAG vazio.")
            return

        batch_size = 50
        for i in range(0, len(documents), batch_size):
            self._collection.add(
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )

        logger.info("RAG: %d documentos indexados em %d tabelas.", len(documents), len(tabelas))
