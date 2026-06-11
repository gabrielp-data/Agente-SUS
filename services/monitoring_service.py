"""Monitoring service — persists query logs in a local SQLite database."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Generator

import pandas as pd

from utils.logger import get_logger

logger = get_logger("monitoring")

# NOTA: SQLite local é efêmero em hosts como o Streamlit Cloud — os logs
# zeram a cada redeploy. Para persistência real, migrar para o PostgreSQL.
DB_PATH = "logs/monitoring.db"

# Preço por 1K tokens (USD) — Claude Sonnet 4.x: $3/M entrada, $15/M saída
PRICE_INPUT_PER_1K = 0.003
PRICE_OUTPUT_PER_1K = 0.015


@dataclass
class QueryLog:
    question: str
    sql: str = ""
    answer: str = ""
    tables_used: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: int = 0
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class MonitoringService:
    """Singleton-style service for query auditing and telemetry."""

    _instance: MonitoringService | None = None

    def __new__(cls) -> MonitoringService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_db()
        return cls._instance

    # ── Setup ────────────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        import os
        os.makedirs("logs", exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS query_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp   TEXT,
                    question    TEXT,
                    sql         TEXT,
                    answer      TEXT,
                    tables_used TEXT,
                    input_tokens  INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    latency_ms    INTEGER DEFAULT 0,
                    error         TEXT DEFAULT ''
                )
                """
            )
            conn.commit()

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        try:
            yield conn
        finally:
            conn.close()

    # ── Write ────────────────────────────────────────────────────────────────

    def log_query(self, entry: QueryLog) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO query_log
                    (timestamp, question, sql, answer, tables_used,
                     input_tokens, output_tokens, latency_ms, error)
                VALUES (?,?,?,?,?,?,?,?,?)
                """,
                (
                    entry.timestamp, entry.question, entry.sql, entry.answer,
                    entry.tables_used, entry.input_tokens, entry.output_tokens,
                    entry.latency_ms, entry.error,
                ),
            )
            conn.commit()
        logger.debug("Query registrada: %s", entry.question[:80])

    # ── Read ─────────────────────────────────────────────────────────────────

    def get_history(self, limit: int = 100) -> pd.DataFrame:
        with self._conn() as conn:
            return pd.read_sql_query(
                "SELECT * FROM query_log ORDER BY id DESC LIMIT ?",
                conn, params=(int(limit),),
            )

    def get_stats(self) -> dict:
        with self._conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT
                    COUNT(*)                    AS total_queries,
                    AVG(latency_ms)             AS avg_latency_ms,
                    SUM(input_tokens)           AS total_input_tokens,
                    SUM(output_tokens)          AS total_output_tokens,
                    SUM(CASE WHEN error != '' THEN 1 ELSE 0 END) AS total_errors
                FROM query_log
                """
            )
            row = cur.fetchone()
        total_q, avg_lat, ti, to_, terr = row or (0, 0, 0, 0, 0)
        cost = ((ti or 0) / 1000 * PRICE_INPUT_PER_1K) + ((to_ or 0) / 1000 * PRICE_OUTPUT_PER_1K)
        return {
            "total_queries": total_q or 0,
            "avg_latency_ms": round(avg_lat or 0, 1),
            "total_input_tokens": ti or 0,
            "total_output_tokens": to_ or 0,
            "total_errors": terr or 0,
            "estimated_cost_usd": round(cost, 4),
        }

    def clear_logs(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM query_log")
            conn.commit()
        logger.info("Logs de monitoramento limpos.")
