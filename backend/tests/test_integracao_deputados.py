import copy

import httpx
import pytest
from sqlalchemy import func, select

from app.coletores.deputados import importar_deputados
from app.coletores.http import ClienteHttp, ErroColeta
from app.models import Deputado, ErroImportacao, Filiacao, FonteImportacao, Mandato

pytestmark = pytest.mark.integracao

BASE = "https://api.teste.invalid/api/v2"

# Payloads sintéticos no formato da API v2 (não são deputados reais).
LISTA = [
    {"id": 1001, "uri": f"{BASE}/deputados/1001", "nome": "Deputada Teste A",
     "siglaPartido": "PTESTE", "uriPartido": f"{BASE}/partidos/1", "siglaUf": "DF",
     "idLegislatura": 57, "urlFoto": "https://exemplo.invalid/1001.jpg",
     "email": "dep.a@exemplo.invalid"},
    {"id": 1002, "uri": f"{BASE}/deputados/1002", "nome": "Deputado Teste B",
     "siglaPartido": "POUTRO", "uriPartido": f"{BASE}/partidos/2", "siglaUf": "SP",
     "idLegislatura": 57, "urlFoto": None, "email": None},
]  # fmt: skip


def detalhe(id_):
    return {
        "dados": {
            "id": id_, "nomeCivil": f"Nome Civil {id_}", "sexo": "F",
            "dataNascimento": "1980-01-31", "ufNascimento": "DF",
            "municipioNascimento": "Brasília",
            "ultimoStatus": {"situacao": "Exercício", "condicaoEleitoral": "Titular",
                             "data": "2023-02-01"},
        }
    }  # fmt: skip


def criar_handler(lista, falhar_detalhe=None):
    def handler(request: httpx.Request):
        caminho = request.url.path
        if caminho.endswith("/deputados"):
            pagina = int(request.url.params.get("pagina", "1"))
            links = []
            if pagina == 1:
                links.append({"rel": "next", "href": f"{BASE}/deputados?pagina=2&itens=1"})
            return httpx.Response(200, json={"dados": [lista[pagina - 1]], "links": links})
        id_ = int(caminho.rsplit("/", 1)[-1])
        if id_ == falhar_detalhe:
            return httpx.Response(404)
        return httpx.Response(200, json=detalhe(id_))

    return handler


def rodar(session, settings, handler):
    with ClienteHttp(settings, transport=httpx.MockTransport(handler)) as cliente:
        return importar_deputados(session, cliente, settings)


def test_importacao_e_idempotencia(session, settings):
    fonte = rodar(session, settings, criar_handler(LISTA))
    assert fonte.status == "sucesso"
    assert (fonte.registros_lidos, fonte.registros_inseridos) == (2, 2)
    assert len(fonte.hash_sha256) == 64
    assert fonte.caminho_arquivo_bruto

    dep = session.scalar(select(Deputado).where(Deputado.id_camara == 1001))
    assert dep.nome_civil == "Nome Civil 1001"
    assert dep.data_nascimento.isoformat() == "1980-01-31"
    assert dep.payload_origem["lista"]["siglaPartido"] == "PTESTE"
    assert session.scalar(select(func.count()).select_from(Mandato)) == 2
    assert session.scalar(select(func.count()).select_from(Filiacao)) == 2

    segunda = rodar(session, settings, criar_handler(LISTA))
    assert (segunda.registros_inseridos, segunda.registros_atualizados) == (0, 0)
    assert segunda.registros_inalterados == 2
    assert session.scalar(select(func.count()).select_from(Deputado)) == 2


def test_mudanca_na_origem_atualiza(session, settings):
    rodar(session, settings, criar_handler(LISTA))
    lista = copy.deepcopy(LISTA)
    lista[0]["siglaPartido"] = "PNOVO"
    fonte = rodar(session, settings, criar_handler(lista))
    assert (fonte.registros_atualizados, fonte.registros_inalterados) == (1, 1)
    partidos = session.scalars(
        select(Filiacao.sigla_partido).join(Deputado).where(Deputado.id_camara == 1001)
    ).all()
    assert sorted(partidos) == ["PNOVO", "PTESTE"]


def test_falha_no_detalhe_registra_erro_e_preserva_registro(session, settings):
    fonte = rodar(session, settings, criar_handler(LISTA, falhar_detalhe=1002))
    assert fonte.status == "parcial"
    assert fonte.registros_inseridos == 2
    erro = session.scalar(select(ErroImportacao))
    assert "1002" in erro.referencia
    assert erro.payload_origem["id"] == 1002


def test_falha_total_marca_importacao(session, settings):
    with pytest.raises(ErroColeta):
        rodar(session, settings, lambda r: httpx.Response(500))
    fonte_falhou = session.scalar(select(FonteImportacao))
    assert fonte_falhou.status == "falha"
    assert "500" in fonte_falhou.mensagem_erro
    assert fonte_falhou.finalizado_em is not None
