"""SQL safety validation — blocks all write/destructive operations."""
from __future__ import annotations

import re

# Keywords that are never allowed
BLOCKED_KEYWORDS: list[str] = [
    "DELETE", "UPDATE", "DROP", "ALTER", "TRUNCATE",
    "INSERT", "CREATE", "GRANT", "REVOKE", "EXEC",
    "EXECUTE", "MERGE", "CALL", "PRAGMA", "ATTACH",
    "DETACH", "VACUUM", "REINDEX",
]

# SQL must start with one of these (after optional CTEs / comments)
ALLOWED_STARTERS: tuple[str, ...] = ("SELECT", "WITH", "EXPLAIN")


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Validate that *sql* is a safe read-only query.

    Returns:
        (True, "")          — query is safe
        (False, reason)     — query is unsafe with explanation
    """
    if not sql or not sql.strip():
        return False, "SQL vazio."

    normalized = re.sub(r"--[^\n]*", " ", sql)          # strip line comments
    normalized = re.sub(r"/\*.*?\*/", " ", normalized, flags=re.DOTALL)  # block comments
    normalized = re.sub(r"\s+", " ", normalized).strip().upper()

    # Must start with an allowed keyword
    if not any(normalized.startswith(kw) for kw in ALLOWED_STARTERS):
        return False, (
            f"Apenas consultas SELECT/WITH/EXPLAIN são permitidas. "
            f"SQL começa com: '{normalized[:30]}...'"
        )

    # Must not contain blocked keywords as whole tokens
    for kw in BLOCKED_KEYWORDS:
        pattern = rf"\b{kw}\b"
        if re.search(pattern, normalized):
            return False, f"Operação '{kw}' não é permitida — somente leitura."

    # Basic injection patterns
    dangerous_patterns = [
        r";\s*(DELETE|UPDATE|DROP|INSERT|ALTER|TRUNCATE)",
        r"UNION\s+ALL\s+SELECT\s+NULL",
        r"1\s*=\s*1\s*--",
        r"OR\s+1\s*=\s*1",
    ]
    for pat in dangerous_patterns:
        if re.search(pat, normalized):
            return False, "Padrão suspeito detectado no SQL."

    return True, ""


def sanitize_sql(sql: str, schema: str = "SUS_SINAN") -> str:
    """
    Remove trailing semicolons, normaliza whitespace e garante que
    todas as tabelas SINAN usem o schema qualificado (SUS_SINAN.tabela).
    """
    sql = sql.strip().rstrip(";").strip()
    sql = _qualify_sinan_tables(sql, schema)
    return sql


# Tabelas SINAN conhecidas
_SINAN_TABLES = [
    "sus_sinan_dengue_mensal",
    "sus_sinan_dengue_anual",
    "sus_sinan_dengue_antigo_mensal",
    "sus_sinan_dengue_antigo_anual",
    "sus_sinan_botulismo_mensal",
    "sus_sinan_chagas_mensal",
]


def _qualify_sinan_tables(sql: str, schema: str) -> str:
    """
    Substitui referências a tabelas SINAN sem schema pelo formato qualificado.
    Ex: 'FROM sus_sinan_dengue_mensal' → 'FROM "SUS_SINAN".sus_sinan_dengue_mensal'
    Não toca em referências que já têm schema (ex: "SUS_SINAN".tabela).
    """
    for table in _SINAN_TABLES:
        # Substitui apenas ocorrências sem schema precedente
        # Padrão: não precedido por ponto (.) ou aspas fechando (")
        pattern = rf'(?<![.\"])\b({re.escape(table)})\b'
        replacement = f'"{schema}".{table}'
        sql = re.sub(pattern, replacement, sql, flags=re.IGNORECASE)
    return sql
