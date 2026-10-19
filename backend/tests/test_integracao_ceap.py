from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.coletores.ceap import ErroFormatoCeap, importar_ceap
from app.models import (
    Deputado,
    Despesa,
    Documento,
    ErroImportacao,
    FonteImportacao,
    Fornecedor,
)
from tests.conftest import criar_zip_ceap, linha_ceap

pytestmark = pytest.mark.integracao


def linhas_exemplo():
    return [
        linha_ceap(),
        linha_ceap(ideDocumento="9000002", vlrLiquido="80.00", vlrDocumento="80.00",
                   urlDocumento=""),
        linha_ceap(ideCadastro="", txNomeParlamentar="LIDERANÇA DO PTESTE",
                   ideDocumento="9000003", txtCNPJCPF="", txtFornecedor="CIA AÉREA X",
                   vlrLiquido="-30.00", urlDocumento=""),
    ]  # fmt: skip


def test_importacao_ceap_e_idempotencia(session, settings, tmp_path):
    session.add(
        Deputado(id_camara=1001, nome="Teste", hash_payload="0" * 64, payload_origem={},
                 coletado_em=func.now())
    )  # fmt: skip
    session.commit()
    arquivo = criar_zip_ceap(tmp_path / "Ano-2024.csv.zip", linhas_exemplo())

    fonte = importar_ceap(session, None, settings, 2024, arquivo)
    assert fonte.status == "sucesso"
    assert (fonte.registros_lidos, fonte.registros_inseridos) == (3, 3)
    assert len(fonte.hash_sha256) == 64

    despesas = session.scalars(select(Despesa).order_by(Despesa.id)).all()
    assert all(d.tipo_gasto == "CEAP" for d in despesas)
    assert despesas[0].valor_liquido == Decimal("150.10")
    assert isinstance(despesas[0].valor_liquido, Decimal)
    assert despesas[0].deputado_id is not None
    assert despesas[2].deputado_id is None
    assert despesas[2].valor_liquido == Decimal("-30.00")
    assert session.scalar(select(func.count()).select_from(Fornecedor)) == 2
    assert session.scalar(select(func.count()).select_from(Documento)) == 1

    repetida = importar_ceap(session, None, settings, 2024, arquivo)
    assert repetida.status == "sem_alteracao"
    assert repetida.registros_lidos == 0

    forcada = importar_ceap(session, None, settings, 2024, arquivo, forcar=True)
    assert forcada.status == "sucesso"
    assert (forcada.registros_inseridos, forcada.registros_inalterados) == (0, 3)
    assert session.scalar(select(func.count()).select_from(Despesa)) == 3


def test_correcao_na_origem_atualiza_despesa(session, settings, tmp_path):
    importar_ceap(
        session, None, settings, 2024, criar_zip_ceap(tmp_path / "a.zip", linhas_exemplo())
    )
    linhas = linhas_exemplo()
    linhas[0]["vlrGlosa"] = "10.00"
    linhas[0]["vlrLiquido"] = "140.10"
    fonte = importar_ceap(session, None, settings, 2024, criar_zip_ceap(tmp_path / "b.zip", linhas))
    assert (fonte.registros_atualizados, fonte.registros_inalterados) == (1, 2)
    despesa = session.scalar(select(Despesa).where(Despesa.id_documento_origem == "9000001"))
    assert despesa.valor_liquido == Decimal("140.10")
    assert despesa.valor_glosa == Decimal("10.00")


def test_linhas_invalidas_registradas(session, settings, tmp_path):
    linhas = [linha_ceap(), linha_ceap(ideDocumento="1", vlrLiquido="abc"), linha_ceap()]
    fonte = importar_ceap(session, None, settings, 2024, criar_zip_ceap(tmp_path / "a.zip", linhas))
    assert fonte.status == "parcial"
    assert (fonte.registros_inseridos, fonte.registros_com_erro) == (1, 2)
    mensagens = session.scalars(select(ErroImportacao.mensagem)).all()
    assert any("monetário" in m for m in mensagens)
    assert any("repetida" in m for m in mensagens)


def test_cabecalho_invalido_marca_falha(session, settings, tmp_path):
    arquivo = criar_zip_ceap(tmp_path / "a.zip", [linha_ceap()], cabecalho=["x", "y"])
    with pytest.raises(ErroFormatoCeap):
        importar_ceap(session, None, settings, 2024, arquivo)
    fonte = session.scalar(select(FonteImportacao))
    assert fonte.status == "falha"
    assert "Colunas obrigatórias ausentes" in fonte.mensagem_erro
    assert session.scalar(select(func.count()).select_from(Despesa)) == 0
