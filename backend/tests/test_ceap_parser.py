import zipfile
from decimal import Decimal

import pytest

from app.coletores.ceap import (
    ErroFormatoCeap,
    chave_fornecedor,
    chave_origem,
    ler_csv_zip,
    normalizar_linha,
    validar_cabecalho,
)
from tests.conftest import CABECALHO_CEAP, criar_zip_ceap, linha_ceap


def test_cabecalho_valido():
    validar_cabecalho(CABECALHO_CEAP)


def test_cabecalho_sem_coluna_obrigatoria_falha():
    with pytest.raises(ErroFormatoCeap, match="vlrLiquido"):
        validar_cabecalho([c for c in CABECALHO_CEAP if c != "vlrLiquido"])


def test_normalizar_linha_tipos_corretos():
    d = normalizar_linha(linha_ceap())
    assert d["tipo_gasto"] == "CEAP"
    assert d["valor_liquido"] == Decimal("150.10")
    assert d["valor_glosa"] == Decimal("0.00")
    assert d["valor_restituicao"] is None
    assert d["data_emissao"].isoformat() == "2024-03-05"
    assert (d["ano"], d["mes"]) == (2024, 3)
    assert d["id_camara_deputado"] == 1001
    assert d["payload_origem"]["urlDocumento"].endswith(".pdf")


def test_normalizar_linha_mes_invalido():
    with pytest.raises(ValueError, match="numMes"):
        normalizar_linha(linha_ceap(numMes="13"))


def test_lideranca_sem_ide_cadastro():
    d = normalizar_linha(linha_ceap(ideCadastro="", txNomeParlamentar="LIDERANÇA DO PTESTE"))
    assert d["id_camara_deputado"] is None


def test_chave_origem_por_documento_e_parcela():
    a = chave_origem(linha_ceap(numParcela="1"))
    b = chave_origem(linha_ceap(numParcela="2"))
    assert a.startswith("ceap:doc:9000001:")
    assert a != b


def test_chave_origem_sem_ide_documento_usa_hash():
    assert chave_origem(linha_ceap(ideDocumento="0")).startswith("ceap:linha:")


def test_chave_fornecedor():
    chave, dados = chave_fornecedor(linha_ceap())
    assert chave == "00000000000191"
    assert dados["tipo_documento"] == "CNPJ"
    chave, dados = chave_fornecedor(linha_ceap(txtCNPJCPF="", txtFornecedor="Cia Aérea X"))
    assert chave == "nome:CIA AEREA X"
    assert dados["cnpj_cpf"] is None


@pytest.mark.parametrize("codificacao", ["utf-8-sig", "latin-1"])
def test_ler_csv_zip_codificacoes(tmp_path, settings, codificacao):
    caminho = criar_zip_ceap(tmp_path / "a.zip", [linha_ceap()], codificacao=codificacao)
    linhas = list(ler_csv_zip(caminho, settings))
    assert len(linhas) == 1
    assert linhas[0][1]["txtDescricao"] == "COMBUSTÍVEIS E LUBRIFICANTES."


def test_ler_csv_zip_cabecalho_invalido(tmp_path, settings):
    caminho = criar_zip_ceap(tmp_path / "a.zip", [linha_ceap()], cabecalho=["a", "b"])
    with pytest.raises(ErroFormatoCeap):
        list(ler_csv_zip(caminho, settings))


def test_zip_com_dois_csv_rejeitado(tmp_path, settings):
    caminho = tmp_path / "a.zip"
    with zipfile.ZipFile(caminho, "w") as zf:
        zf.writestr("a.csv", "x")
        zf.writestr("b.csv", "y")
    with pytest.raises(ErroFormatoCeap, match="Esperado 1 CSV"):
        list(ler_csv_zip(caminho, settings))


def test_arquivo_nao_zip(tmp_path, settings):
    caminho = tmp_path / "a.zip"
    caminho.write_bytes(b"<html>erro</html>")
    with pytest.raises(ErroFormatoCeap, match="zip"):
        list(ler_csv_zip(caminho, settings))
