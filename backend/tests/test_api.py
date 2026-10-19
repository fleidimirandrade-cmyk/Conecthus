import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db import get_session
from app.main import app
from app.models import FonteImportacao


class SessaoQuebrada:
    def execute(self, *_a, **_k):
        raise OperationalError("SELECT 1", {}, Exception("conexão recusada"))


@pytest.fixture
def cliente_api():
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health_banco_indisponivel(cliente_api):
    app.dependency_overrides[get_session] = lambda: SessaoQuebrada()
    resposta = cliente_api.get("/api/v1/health")
    assert resposta.status_code == 503
    assert resposta.json()["banco_de_dados"] == "indisponivel"


@pytest.mark.integracao
def test_health_ok(cliente_api, session):
    app.dependency_overrides[get_session] = lambda: session
    resposta = cliente_api.get("/api/v1/health")
    assert resposta.status_code == 200
    assert resposta.json() == {"status": "ok", "banco_de_dados": "ok", "versao": "0.1.0"}


@pytest.mark.integracao
def test_status_fontes_sem_importacoes(cliente_api, session):
    app.dependency_overrides[get_session] = lambda: session
    corpo = cliente_api.get("/api/v1/fontes/status").json()
    tipos = {f["tipo"]: f for f in corpo["fontes"]}
    assert set(tipos) == {"deputados_api", "ceap_arquivo_anual"}
    assert all(f["ultima_importacao"] is None for f in corpo["fontes"])


@pytest.mark.integracao
def test_status_fontes_com_importacao(cliente_api, session):
    session.add(
        FonteImportacao(
            tipo="ceap_arquivo_anual",
            url="https://x.invalid",
            parametros={"ano": 2024},
            status="falha",
            mensagem_erro="HTTP 500",
        )
    )
    session.commit()
    app.dependency_overrides[get_session] = lambda: session
    corpo = cliente_api.get("/api/v1/fontes/status").json()
    ceap = next(f for f in corpo["fontes"] if f["tipo"] == "ceap_arquivo_anual")
    assert ceap["ultima_importacao"]["status"] == "falha"
    assert ceap["ultima_importacao"]["mensagem_erro"] == "HTTP 500"
    assert ceap["ultima_importacao_bem_sucedida_em"] is None
