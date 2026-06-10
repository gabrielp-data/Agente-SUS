"""Application settings loaded from environment variables."""
from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Localiza o .env relativo a este arquivo (raiz do projeto)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH, override=True)

# Streamlit Community Cloud: copia os secrets do painel para o ambiente,
# de modo que os.getenv() funcione igual ao .env local (sem precisar de .env).
try:  # pragma: no cover
    import streamlit as _st

    _secrets = getattr(_st, "secrets", None)
    if _secrets is not None:
        for _k in list(_secrets.keys()):
            os.environ.setdefault(_k, str(_secrets[_k]))
except Exception:
    # Fora do runtime Streamlit (ou sem secrets configurados) — ignora.
    pass


def _region_from_endpoint(endpoint: str) -> str:
    """Extrai região a partir da URL do endpoint, ex: us-east-2."""
    m = re.search(r"bedrock-runtime\.([a-z0-9-]+)\.amazonaws\.com", endpoint)
    return m.group(1) if m else "us-east-1"


class Settings:
    """Central configuration object populated from .env / environment."""

    # ── Bedrock ──────────────────────────────────────────────────────────────
    bedrock_api_key: str = os.getenv("BEDROCK_API_KEY", "")
    bedrock_endpoint: str = os.getenv(
        "BEDROCK_ENDPOINT", "https://bedrock-runtime.us-east-2.amazonaws.com"
    )
    bedrock_model_id: str = os.getenv(
        "BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6"
    )

    # ── AWS credentials (fallback quando API key não está configurada) ───────
    aws_access_key_id: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_access_key: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_session_token: Optional[str] = os.getenv("AWS_SESSION_TOKEN")

    @property
    def aws_region(self) -> str:
        """Região derivada do endpoint ou da variável AWS_REGION."""
        explicit = os.getenv("AWS_REGION")
        if explicit:
            return explicit
        return _region_from_endpoint(self.bedrock_endpoint)

    # ── PostgreSQL ────────────────────────────────────────────────────────────
    db_host: str = os.getenv("DB_HOST", "localhost")
    db_port: int = int(os.getenv("DB_PORT", "5432"))
    db_name: str = os.getenv("DB_NAME", "iesb")
    db_schema: str = os.getenv("DB_SCHEMA", "SUS_SINAN")
    db_user: str = os.getenv("DB_USER", "postgres")
    db_password: str = os.getenv("DB_PASSWORD", "")

    # ── App behaviour ─────────────────────────────────────────────────────────
    max_sql_rows: int = int(os.getenv("MAX_SQL_ROWS", "500"))
    sql_timeout: int = int(os.getenv("SQL_TIMEOUT", "30"))
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    # ── Available tables ──────────────────────────────────────────────────────
    sinan_tables: list[str] = [
        "sus_sinan_dengue_antigo_anual",
        "sus_sinan_dengue_antigo_mensal",
        "sus_sinan_dengue_anual",
        "sus_sinan_dengue_mensal",
        "sus_sinan_botulismo_mensal",
        "sus_sinan_chagas_mensal",
    ]

    # ── Model catalogue ───────────────────────────────────────────────────────
    # Todos os modelos usam prefixo "us." (cross-region inference profile).
    # Verificado como ACTIVE e funcional em us-east-2 em junho/2026.
    available_models: dict[str, str] = {
        "Claude Sonnet 4.6 (recomendado)": "us.anthropic.claude-sonnet-4-6",
        "Claude Haiku 4.5": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "Amazon Nova Pro": "us.amazon.nova-pro-v1:0",
        "Amazon Nova Lite": "us.amazon.nova-lite-v1:0",
        "Amazon Nova 2 Lite": "us.amazon.nova-2-lite-v1:0",
        "Amazon Nova Micro": "us.amazon.nova-micro-v1:0",
    }

    @property
    def use_api_key(self) -> bool:
        """True when a Bedrock API key is configured."""
        return bool(self.bedrock_api_key)

    @property
    def db_dsn(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def reload(self) -> None:
        """Re-read .env so credential updates take effect without restart."""
        load_dotenv(str(_ENV_PATH), override=True)
        for field in [
            "BEDROCK_API_KEY", "BEDROCK_ENDPOINT", "BEDROCK_MODEL_ID",
            "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
            "DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD",
        ]:
            val = os.getenv(field)
            attr = field.lower()
            if val is not None and hasattr(self, attr):
                setattr(self, attr, val)

    def save_to_env(self, updates: dict[str, str]) -> None:
        """Persist key=value pairs to .env file (sempre no diretório do projeto)."""
        env_path = str(_ENV_PATH)
        lines: list[str] = []
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

        updated_keys: set[str] = set()
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                    continue
            new_lines.append(line)

        for key, val in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")

        with open(env_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        self.reload()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
