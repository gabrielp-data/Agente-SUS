"""Testes do enriquecimento geográfico (UF → sigla, município → nome)."""
import pandas as pd

from agents.nodes import _humanize_chart_df, enrich_geo
from utils.geo import SIGLA_UF, UF_SIGLA, municipio_nome


def test_codigo_uf_vira_sigla():
    df = pd.DataFrame({"uf": ["35", "31", "41"], "total": [3, 2, 1]})
    out = _humanize_chart_df(df)
    assert out["uf"].tolist() == ["SP", "MG", "PR"]


def test_codigo_municipio_ganha_coluna_nome():
    df = pd.DataFrame({"codigo_municipio": ["530010", "355030"], "total": [9, 8]})
    out = enrich_geo(df)
    assert "municipio" in out.columns
    assert out["municipio"].tolist() == ["Brasília (DF)", "São Paulo (SP)"]
    # o código original é preservado
    assert out["codigo_municipio"].tolist() == ["530010", "355030"]


def test_municipio_nome_lookup():
    assert municipio_nome("530010") == "Brasília"
    assert municipio_nome("000000") is None


def test_coluna_de_ano_nao_e_alterada():
    df = pd.DataFrame({"ano": ["2022", "2023"], "total": [1, 2]})
    out = _humanize_chart_df(df)
    assert out["ano"].tolist() == ["2022", "2023"]


def test_colunas_numericas_intactas():
    df = pd.DataFrame({"uf": ["35"], "total": [11027]})
    out = _humanize_chart_df(df)
    assert out["total"].iloc[0] == 11027


def test_mapas_geo_sao_inversos():
    assert all(SIGLA_UF[sigla] == cod for cod, sigla in UF_SIGLA.items())
    assert len(UF_SIGLA) == 27  # 26 estados + DF
