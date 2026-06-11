"""Testes da formatação numérica em padrão brasileiro."""
from components.ui import fmt_br, fmt_br_decimal


class TestFmtBr:
    def test_milhares(self):
        assert fmt_br(1234567) == "1.234.567"

    def test_numero_pequeno(self):
        assert fmt_br(42) == "42"

    def test_none_vira_travessao(self):
        assert fmt_br(None) == "—"

    def test_float_arredonda(self):
        assert fmt_br(1234.6) == "1.235"

    def test_valor_invalido_nao_explode(self):
        assert fmt_br("abc") == "abc"


class TestFmtBrDecimal:
    def test_decimal_brasileiro(self):
        assert fmt_br_decimal(1234.5, 1) == "1.234,5"

    def test_duas_casas(self):
        assert fmt_br_decimal(0.04, 2) == "0,04"

    def test_none_vira_travessao(self):
        assert fmt_br_decimal(None) == "—"
