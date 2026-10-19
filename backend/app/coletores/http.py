"""Cliente HTTP com retry, backoff exponencial com jitter e paginação segura."""

import logging
import random
import time
from collections.abc import Callable, Iterator
from typing import Any
from urllib.parse import urlparse

import httpx

from app.config import Settings

logger = logging.getLogger(__name__)

STATUS_REPETIVEIS = {429, 500, 502, 503, 504}
USER_AGENT = "FiscalizaBrasil/0.1 (+coleta de dados abertos)"


class ErroColeta(Exception):
    """Falha definitiva ao obter um recurso de uma fonte externa."""


class ClienteHttp:
    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        dormir: Callable[[float], None] = time.sleep,
    ) -> None:
        self.settings = settings
        self._dormir = dormir
        self._client = httpx.Client(
            timeout=settings.http_timeout_segundos,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            transport=transport,
        )

    def __enter__(self) -> "ClienteHttp":
        return self

    def __exit__(self, *exc: object) -> None:
        self._client.close()

    def _espera(self, tentativa: int, resposta: httpx.Response | None) -> float:
        if resposta is not None:
            retry_after = resposta.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                return min(float(retry_after), self.settings.http_backoff_max_segundos)
        base = self.settings.http_backoff_base_segundos * (2 ** (tentativa - 1))
        return min(base, self.settings.http_backoff_max_segundos) * (0.5 + random.random() / 2)

    def _com_retry(self, url: str, executar: Callable[[], Any]) -> Any:
        max_tentativas = self.settings.http_max_tentativas
        for tentativa in range(1, max_tentativas + 1):
            resposta: httpx.Response | None = None
            try:
                return executar()
            except httpx.HTTPStatusError as exc:
                resposta = exc.response
                if resposta.status_code not in STATUS_REPETIVEIS:
                    raise ErroColeta(f"HTTP {resposta.status_code} em {url}") from exc
                erro = f"HTTP {resposta.status_code}"
            except httpx.TransportError as exc:
                erro = f"{type(exc).__name__}: {exc}"
            if tentativa == max_tentativas:
                raise ErroColeta(f"Falha após {tentativa} tentativas em {url}: {erro}")
            espera = self._espera(tentativa, resposta)
            logger.warning(
                "requisicao_falhou_nova_tentativa",
                extra={"url": url, "tentativa": tentativa, "erro": erro, "espera_s": espera},
            )
            self._dormir(espera)
        raise AssertionError("inalcançável")

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        def executar() -> dict[str, Any]:
            resposta = self._client.get(url, params=params, headers={"Accept": "application/json"})
            resposta.raise_for_status()
            return resposta.json()

        return self._com_retry(url, executar)

    def baixar_arquivo(self, url: str, abrir_destino: Callable[[], Any], tamanho_max: int) -> dict:
        """Baixa em streaming. `abrir_destino` deve devolver um arquivo binário novo
        a cada tentativa. Retorna metadados HTTP relevantes."""

        def executar() -> dict:
            with self._client.stream("GET", url) as resposta:
                resposta.raise_for_status()
                total = 0
                with abrir_destino() as destino:
                    for bloco in resposta.iter_bytes(chunk_size=1024 * 1024):
                        total += len(bloco)
                        if total > tamanho_max:
                            raise ErroColeta(f"Arquivo excede {tamanho_max} bytes: {url}")
                        destino.write(bloco)
                return {
                    "url_final": str(resposta.url),
                    "status_http": resposta.status_code,
                    "content_type": resposta.headers.get("Content-Type"),
                    "last_modified": resposta.headers.get("Last-Modified"),
                    "etag": resposta.headers.get("ETag"),
                }

        return self._com_retry(url, executar)

    def paginar(self, url: str, params: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
        """Segue os links `rel=next` da API da Câmara.

        Proteções: limite de páginas, detecção de ciclo e recusa de links
        para outro host.
        """
        host_inicial = urlparse(url).netloc
        visitadas: set[str] = set()
        proxima: str | None = url
        proximos_params: dict[str, Any] | None = params
        paginas = 0
        while proxima:
            if proxima in visitadas:
                raise ErroColeta(f"Ciclo de paginação detectado em {proxima}")
            if urlparse(proxima).netloc != host_inicial:
                raise ErroColeta(f"Link de paginação para host inesperado: {proxima}")
            paginas += 1
            if paginas > self.settings.paginacao_max_paginas:
                raise ErroColeta(
                    f"Limite de {self.settings.paginacao_max_paginas} páginas atingido"
                )
            visitadas.add(proxima)
            corpo = self.get_json(proxima, params=proximos_params)
            yield proxima, corpo
            proximos_params = None  # o link "next" já contém os parâmetros
            proxima = next(
                (link.get("href") for link in corpo.get("links", []) if link.get("rel") == "next"),
                None,
            )
