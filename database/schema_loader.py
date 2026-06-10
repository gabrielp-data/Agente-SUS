"""Load table schemas from PostgreSQL information_schema."""
from __future__ import annotations

from config.settings import get_settings
from database.connection import get_connection
from utils.logger import get_logger

logger = get_logger("schema_loader")

SchemaDict = dict[str, list[dict]]


def load_schema() -> SchemaDict:
    """
    Read column metadata for all configured SINAN tables.

    Returns:
        {table_name: [{"column": str, "type": str, "nullable": str}]}
    """
    settings = get_settings()
    schema: SchemaDict = {}

    with get_connection() as conn:
        with conn.cursor() as cur:
            for table in settings.sinan_tables:
                cur.execute(
                    """
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                      AND table_schema = %s
                    ORDER BY ordinal_position
                    """,
                    (table, settings.db_schema),
                )
                rows = cur.fetchall()
                if rows:
                    schema[table] = [
                        {"column": r[0], "type": r[1], "nullable": r[2]}
                        for r in rows
                    ]
                    logger.debug("Tabela '%s': %d colunas carregadas.", table, len(rows))
                else:
                    logger.warning("Tabela '%s' não encontrada no banco.", table)

    logger.info("Schema carregado: %d tabelas.", len(schema))
    return schema


def schema_to_prompt(schema: SchemaDict) -> str:
    """Format schema as a readable string for injection into LLM prompts."""
    lines: list[str] = []
    for table, cols in schema.items():
        lines.append(f"\nTabela: {table}")
        for c in cols:
            nullable = " (nullable)" if c["nullable"] == "YES" else ""
            lines.append(f"  • {c['column']}  [{c['type']}{nullable}]")
    return "\n".join(lines)
