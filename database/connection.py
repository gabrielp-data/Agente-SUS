"""PostgreSQL connection helpers — pool de conexões com timeout e LIMIT defensivo."""
from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from typing import Generator

import pandas as pd
import psycopg2
import psycopg2.pool
from psycopg2 import OperationalError

from config.settings import get_settings
from utils.logger import get_logger

logger = get_logger("database")

# Pool global (recriado se as credenciais mudarem via Configurações)
_pool: psycopg2.pool.SimpleConnectionPool | None = None
_pool_key: tuple | None = None
_pool_lock = threading.Lock()


def _get_pool() -> psycopg2.pool.SimpleConnectionPool:
    """Retorna o pool, criando/recriando quando as credenciais mudam."""
    global _pool, _pool_key
    settings = get_settings()
    key = (
        settings.db_host, settings.db_port, settings.db_name,
        settings.db_user, settings.db_password, settings.sql_timeout,
    )
    with _pool_lock:
        if _pool is None or _pool_key != key:
            if _pool is not None:
                try:
                    _pool.closeall()
                except Exception:
                    pass
            _pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=4,
                host=settings.db_host,
                port=settings.db_port,
                dbname=settings.db_name,
                user=settings.db_user,
                password=settings.db_password,
                connect_timeout=10,
                options=f"-c statement_timeout={settings.sql_timeout * 1000}",
            )
            _pool_key = key
            logger.info("Pool de conexões criado (max=4).")
    return _pool


@contextmanager
def get_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """Context manager que empresta uma conexão do pool e a devolve limpa."""
    settings = get_settings()
    pool = _get_pool()
    conn = None
    try:
        conn = pool.getconn()
        # search_path por checkout — round trip barato, garante o schema certo
        with conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{settings.db_schema}", public;')
        conn.commit()
        yield conn
    except OperationalError as exc:
        logger.error("Falha ao conectar ao PostgreSQL: %s", exc)
        raise
    finally:
        if conn is not None:
            try:
                conn.rollback()  # limpa transações pendentes antes de devolver
                pool.putconn(conn)
            except Exception:
                try:
                    pool.putconn(conn, close=True)
                except Exception:
                    pass


def _ensure_limit(sql: str, max_rows: int) -> str:
    """Acrescenta LIMIT no servidor quando a query não tem um.

    Evita baixar centenas de milhares de linhas pela rede para depois
    truncar no pandas (a tabela mensal de dengue tem 650k+ linhas).
    """
    if re.search(r"\bLIMIT\s+\d+", sql, flags=re.IGNORECASE):
        return sql
    return f"{sql.rstrip().rstrip(';')} LIMIT {max_rows}"


def execute_query(sql: str) -> tuple[pd.DataFrame | None, str | None]:
    """
    Execute a SELECT query and return (DataFrame, None) on success,
    or (None, error_message) on failure.
    """
    settings = get_settings()
    sql = _ensure_limit(sql, settings.max_sql_rows)
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
