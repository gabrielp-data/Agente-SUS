"""Testes da detecção de perguntas conversacionais (heurística do agente)."""
import pytest

from agents.nodes import _is_conversational


@pytest.mark.parametrize("pergunta", [
    "oi",
    "Bom dia",
    "obrigado!",
    "qual foi a ultima pergunta?",
    "qual foi a última pergunta?",
    "o que voce disse antes?",
    "resuma nossa conversa",
    "o que voce faz?",
    "oq vc consgue me responder ?",
    "me ajuda",
    "quais doencas tem a base?",
    "que tabelas existem?",
    "o que posso consultar",
])
def test_detecta_conversacional(pergunta):
    assert _is_conversational(pergunta)


@pytest.mark.parametrize("pergunta", [
    "quantos casos de dengue em Brasilia em 2023?",
    "compare dengue entre SP e RJ",
    "qual UF teve mais obitos por dengue?",
    "tendencia mensal de dengue no DF em 2024",
    "casos de botulismo por ano",
])
def test_nao_confunde_pergunta_de_dados(pergunta):
    assert not _is_conversational(pergunta)
