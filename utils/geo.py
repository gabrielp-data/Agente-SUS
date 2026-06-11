"""Mapeamentos geográficos IBGE — fonte única para todo o projeto."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

_MUNICIPIOS_PATH = Path(__file__).resolve().parent.parent / "data" / "municipios_ibge.json"

# Código IBGE da UF (2 primeiros dígitos do código do município) → sigla
UF_SIGLA: dict[str, str] = {
    "11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP",
    "17": "TO", "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB",
    "26": "PE", "27": "AL", "28": "SE", "29": "BA", "31": "MG", "32": "ES",
    "33": "RJ", "35": "SP", "41": "PR", "42": "SC", "43": "RS", "50": "MS",
    "51": "MT", "52": "GO", "53": "DF",
}

# Sigla → código IBGE (inverso)
SIGLA_UF: dict[str, str] = {v: k for k, v in UF_SIGLA.items()}


@lru_cache(maxsize=1)
def _municipios() -> dict[str, str]:
    """Mapa código IBGE de 6 dígitos → nome do município (carregado uma vez)."""
    try:
        with open(_MUNICIPIOS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def municipio_nome(codigo: str) -> str | None:
    """Nome do município a partir do código IBGE de 6 dígitos (sem dígito verificador)."""
    return _municipios().get(str(codigo).strip())


def municipio_label(codigo: str) -> str:
    """Rótulo legível: 'Nome (UF)' — cai para o próprio código se não encontrar."""
    cod = str(codigo).strip()
    nome = municipio_nome(cod)
    if not nome:
        return cod
    sigla = UF_SIGLA.get(cod[:2], "")
    return f"{nome} ({sigla})" if sigla else nome
