"""PostgreSQL connection helpers with timeout support."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import pandas as pd
import psycopg2
import psycopg2.extras
from psycopg2 import OperationalError

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger("database")


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager that yields a PostgreSQL connection."""
    settings = get_settings()
    conn = None
    try:
        conn = psycopg2.connect(
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
            connect_timeout=10,
            options=f"-c statement_timeout={settings.sql_timeout * 1000}",
        )
        # Força o search_path via SET após conectar (mais confiável)
        with conn.cursor() as cur:
            cur.execute(
                f'SET search_path TO "{settings.db_schema}", public;'
            )
        conn.commit()
        yield conn
    except OperationalError as exc:
        logger.error("Falha ao conectar ao PostgreSQL: %s", exc)
        raise
    finally:
        if conn and not conn.closed:
            conn.close()


def execute_query(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Execute a SELECT query and return (DataFrame, None) on success,
    or (None, error_message) on failure.
    """
    settings = get_settings()
    try:
        with get_connection() as conn:
            df = pd.read_sql_query(sql, conn)
            if len(df) > settings.max_sql_rows:
                df = df.head(settings.max_sql_rows)
                logger.warning("Resultado truncado para %d linhas.", settings.max_sql_rows)
            logger.info("Query executada com sucesso — %d linhas retornadas.", len(df))
            return df, None
    except Exception as exc:
        logger.error("Erro ao executar SQL: %s", exc)
        return None, str(exc)


def test_connection() -> tuple[bool, str]:
    """Return (True, version_string) or (False, error_message)."""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                version = cur.fetchone()[0]
        return True, version
    except Exception as exc:
        return False, str(exc)
