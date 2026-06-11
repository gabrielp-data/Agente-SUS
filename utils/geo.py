"""Mapeamentos geográficos IBGE — fonte única para todo o projeto."""
from __future__ import annotations

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
