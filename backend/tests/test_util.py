from datetime import date
from decimal import Decimal

import pytest

from app.coletores.util import (
    classificar_documento,
    data_iso,
    decimal_monetario,
    hash_payload,
    inteiro,
    normalizar_nome,
    somente_digitos,
)


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("150.10", Decimal("150.10")),
        ("150,1", Decimal("150.10")),
        ("1.234,56", Decimal("1234.56")),
        ("-30.00", Decimal("-30.00")),
        ("0", Decimal("0.00")),
        ("R$ 10,00", Decimal("10.00")),
        ("", None),
        (None, None),
    ],
)
def test_decimal_monetario(entrada, esperado):
    resultado = decimal_monetario(entrada)
    assert resultado == esperado
    if resultado is not None:
        assert isinstance(resultado, Decimal)


def test_decimal_monetario_invalido():
    with pytest.raises(ValueError):
        decimal_monetario("abc")


def test_decimal_preserva_precisao_sem_float():
    assert decimal_monetario("0.1") + decimal_monetario("0.2") == Decimal("0.30")


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("2024-03-05T00:00:00", date(2024, 3, 5)),
        ("2024-03-05", date(2024, 3, 5)),
        ("05/03/2024", date(2024, 3, 5)),
        ("", None),
    ],
)
def test_data_iso(entrada, esperado):
    assert data_iso(entrada) == esperado


def test_data_invalida():
    with pytest.raises(ValueError):
        data_iso("2024-13-40")


def test_inteiro():
    assert inteiro("57") == 57
    assert inteiro(" ") is None
    with pytest.raises(ValueError):
        inteiro("x")


def test_hash_payload_estavel_independente_da_ordem():
    assert hash_payload({"a": 1, "b": "ç"}) == hash_payload({"b": "ç", "a": 1})
    assert hash_payload({"a": 1}) != hash_payload({"a": 2})
    assert len(hash_payload({})) == 64


def test_documentos():
    assert somente_digitos("00.000.000/0001-91") == "00000000000191"
    assert classificar_documento("00000000000191") == "CNPJ"
    assert classificar_documento("12345678901") == "CPF"
    assert classificar_documento(None) == "OUTRO"
    assert normalizar_nome("  Posto  São João ltda ") == "POSTO SAO JOAO LTDA"
