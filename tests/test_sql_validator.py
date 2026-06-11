"""Testes do validador de SQL — a barreira de segurança do agente."""
import pytest

from utils.sql_validator import sanitize_sql, validate_sql


class TestValidateSql:
    @pytest.mark.parametrize("sql", [
        "SELECT * FROM sus_sinan_dengue_anual LIMIT 10",
        "WITH t AS (SELECT 1) SELECT * FROM t",
        "EXPLAIN SELECT 1",
        "select sum(casos_ano) from sus_sinan_dengue_anual where ano = '2023'",
    ])
    def test_aceita_consultas_de_leitura(self, sql):
        ok, msg = validate_sql(sql)
        assert ok, msg

    @pytest.mark.parametrize("sql", [
        "DELETE FROM sus_sinan_dengue_anual",
        "DROP TABLE sus_sinan_dengue_anual",
        "UPDATE sus_sinan_dengue_anual SET casos_ano = 0",
        "INSERT INTO x VALUES (1)",
        "TRUNCATE sus_sinan_dengue_anual",
        "ALTER TABLE x ADD COLUMN y int",
        "GRANT ALL ON x TO public",
        "SELECT 1; DELETE FROM x",
    ])
    def test_bloqueia_operacoes_de_escrita(self, sql):
        ok, _ = validate_sql(sql)
        assert not ok

    def test_bloqueia_sql_vazio(self):
        ok, _ = validate_sql("")
        assert not ok

    def test_bloqueia_keyword_escondida_em_comentario(self):
        # comentários são removidos antes da validação — o DELETE real é pego
        ok, _ = validate_sql("SELECT 1 /* ok */; DELETE FROM x")
        assert not ok


class TestSanitizeSql:
    def test_qualifica_tabela_sem_schema(self):
        out = sanitize_sql("SELECT * FROM sus_sinan_dengue_mensal LIMIT 5")
        assert '"SUS_SINAN".sus_sinan_dengue_mensal' in out

    def test_nao_duplica_schema_existente(self):
        sql = 'SELECT * FROM "SUS_SINAN".sus_sinan_dengue_anual'
        out = sanitize_sql(sql)
        assert out.count("SUS_SINAN") == 1

    def test_qualifica_todas_em_join(self):
        sql = ("SELECT a.casos_mes FROM sus_sinan_dengue_mensal a "
               "JOIN sus_sinan_dengue_antigo_mensal b ON a.ano = b.ano")
        out = sanitize_sql(sql)
        assert out.count('"SUS_SINAN".') == 2

    def test_remove_ponto_e_virgula_final(self):
        assert not sanitize_sql("SELECT 1;").endswith(";")
