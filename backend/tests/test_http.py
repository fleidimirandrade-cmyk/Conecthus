import httpx
import pytest

from app.coletores.http import ClienteHttp, ErroColeta

BASE = "https://api.teste.invalid/api/v2"


def cliente_com(settings, handler, esperas=None):
    dormir = (lambda s: esperas.append(s)) if esperas is not None else (lambda s: None)
    return ClienteHttp(settings, transport=httpx.MockTransport(handler), dormir=dormir)


def test_retry_em_erro_temporario(settings):
    chamadas = []

    def handler(request):
        chamadas.append(request)
        if len(chamadas) < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    esperas: list[float] = []
    with cliente_com(settings, handler, esperas) as cliente:
        assert cliente.get_json(f"{BASE}/x") == {"ok": True}
    assert len(chamadas) == 3
    assert len(esperas) == 2


def test_respeita_retry_after(settings):
    chamadas = []

    def handler(request):
        chamadas.append(request)
        if len(chamadas) == 1:
            return httpx.Response(429, headers={"Retry-After": "7"})
        return httpx.Response(200, json={})

    esperas: list[float] = []
    with cliente_com(settings, handler, esperas) as cliente:
        cliente.get_json(f"{BASE}/x")
    assert esperas == [7.0]


def test_retry_em_falha_de_rede(settings):
    chamadas = []

    def handler(request):
        chamadas.append(request)
        if len(chamadas) == 1:
            raise httpx.ConnectError("sem rede", request=request)
        return httpx.Response(200, json={"ok": 1})

    with cliente_com(settings, handler) as cliente:
        assert cliente.get_json(f"{BASE}/x") == {"ok": 1}


def test_erro_definitivo_nao_repete(settings):
    chamadas = []

    def handler(request):
        chamadas.append(request)
        return httpx.Response(404)

    with cliente_com(settings, handler) as cliente, pytest.raises(ErroColeta, match="404"):
        cliente.get_json(f"{BASE}/x")
    assert len(chamadas) == 1


def test_esgota_tentativas(settings):
    with cliente_com(settings, lambda r: httpx.Response(500)) as cliente:
        with pytest.raises(ErroColeta, match="3 tentativas"):
            cliente.get_json(f"{BASE}/x")


def _pagina(n, total):
    links = [{"rel": "self", "href": f"{BASE}/deputados?pagina={n}"}]
    if n < total:
        links.append({"rel": "next", "href": f"{BASE}/deputados?pagina={n + 1}&itens=1"})
    return {"dados": [{"id": n}], "links": links}


def test_paginacao_segue_next(settings):
    def handler(request):
        return httpx.Response(200, json=_pagina(int(request.url.params["pagina"]), 3))

    with cliente_com(settings, handler) as cliente:
        paginas = list(cliente.paginar(f"{BASE}/deputados", {"pagina": 1, "itens": 1}))
    assert [c["dados"][0]["id"] for _, c in paginas] == [1, 2, 3]


def test_paginacao_detecta_ciclo(settings):
    corpo = {"dados": [], "links": [{"rel": "next", "href": f"{BASE}/deputados"}]}
    with cliente_com(settings, lambda r: httpx.Response(200, json=corpo)) as cliente:
        with pytest.raises(ErroColeta, match="Ciclo"):
            list(cliente.paginar(f"{BASE}/deputados", {}))


def test_paginacao_recusa_outro_host(settings):
    corpo = {"dados": [], "links": [{"rel": "next", "href": "https://malicioso.invalid/x"}]}
    with cliente_com(settings, lambda r: httpx.Response(200, json=corpo)) as cliente:
        with pytest.raises(ErroColeta, match="host inesperado"):
            list(cliente.paginar(f"{BASE}/deputados", {}))


def test_paginacao_limite_de_paginas(settings):
    settings.paginacao_max_paginas = 2

    def handler(request):
        return httpx.Response(200, json=_pagina(int(request.url.params["pagina"]), 10))

    with cliente_com(settings, handler) as cliente:
        with pytest.raises(ErroColeta, match="Limite"):
            list(cliente.paginar(f"{BASE}/deputados", {"pagina": 1}))


def test_download_respeita_tamanho_maximo(settings, tmp_path):
    destino = tmp_path / "arq"
    with cliente_com(settings, lambda r: httpx.Response(200, content=b"x" * 100)) as cliente:
        with pytest.raises(ErroColeta, match="excede"):
            cliente.baixar_arquivo(f"{BASE}/a.zip", lambda: destino.open("wb"), 10)
