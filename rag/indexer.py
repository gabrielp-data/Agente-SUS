"""Índice leve, em memória, do dicionário SINAN (sem ChromaDB).

Para ~70 campos de um dicionário estático, uma busca por sobreposição de termos
é suficiente, instantânea e sem dependências pesadas (sqlite/protobuf/onnx).
"""
from __future__ import annotations

import json
import os
import re
import unicodedata

from pathlib import Path

from utils.logger import get_logger

logger = get_logger("rag.indexer")

# Caminho absoluto — funciona independentemente do diretório de execução
DICT_PATH = str(Path(__file__).resolve().parent.parent / "data" / "dicionario_sinan.json")


def normalize(text: str) -> str:
    """Minúsculas + sem acentos."""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def tokenize(text: str) -> set[str]:
    """Tokens alfanuméricos normalizados (sem acentos, minúsculos)."""
    return set(re.findall(r"[a-z0-9_]+", normalize(text)))


class RAGIndexer:
    """Carrega o dicionário e expõe os documentos para busca em memória."""

    def __init__(self) -> None:
        self._docs: list[dict] | None = None

    @property
    def documents(self) -> list[dict]:
        if self._docs is None:
            self._docs = self._build()
        return self._docs

    def rebuild_index(self) -> None:
        """Recarrega o dicionário do disco."""
        self._docs = self._build()
        logger.info("Índice RAG (memória) reconstruído: %d documentos.", len(self._docs))

    # ── Private ───────────────────────────────────────────────────────────────

    def _build(self) -> list[dict]:
        if not os.path.exists(DICT_PATH):
            logger.warning("Dicionário não encontrado em %s — RAG vazio.", DICT_PATH)
            return []

        with open(DICT_PATH, encoding="utf-8") as f:
            data = json.load(f)

        tabelas = data.get("tabelas") or data.get("tables") or {}
        docs: list[dict] = []

        for table_name, info in tabelas.items():
            table_desc  = info.get("descricao")     or info.get("description", "")
            disease     = info.get("doenca")        or info.get("disease", "")
            granularity = info.get("granularidade") or info.get("granularity", "")
            colunas     = info.get("colunas")       or info.get("columns") or []

            for col in colunas:
                nome    = col.get("nome")      or col.get("name", "")
                tipo    = col.get("tipo")      or col.get("type", "")
                desc    = col.get("descricao") or col.get("description", "")
                exemplo = col.get("exemplo")   or col.get("example", "")

                text = (
                    f"Tabela: {table_name} | Doença: {disease} | "
                    f"Granularidade: {granularity} | Coluna: {nome} | "
                    f"Tipo: {tipo} | Descrição: {desc}"
                )
                if exemplo:
                    text += f" | Exemplo: {exemplo}"

                docs.append({
                    "text": text,
                    "table": table_name,
                    "column": nome,
                    "norm": normalize(f"{table_name} {nome} {desc} {disease}"),
                    "tokens": tokenize(f"{table_name} {nome} {desc} {disease} {tipo}"),
                })

            # Documento da tabela
            docs.append({
                "text": (
                    f"Tabela: {table_name} | Doença: {disease} | "
                    f"Granularidade: {granularity} | Descrição: {table_desc}"
                ),
                "table": table_name,
                "column": "_table_",
                "norm": normalize(f"{table_name} {disease} {table_desc}"),
                "tokens": tokenize(f"{table_name} {disease} {table_desc} {granularity}"),
            })

        logger.info("RAG: %d documentos carregados de %d tabelas.", len(docs), len(tabelas))
        return docs
