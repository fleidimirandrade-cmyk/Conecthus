"""Coletor da API de Dados Abertos da Câmara: GET /deputados e GET /deputados/{id}.

Campos usados (API v2):
- lista (/deputados): id, nome, siglaPartido, uriPartido, siglaUf, idLegislatura,
  urlFoto, email; paginação por `links[rel=next]`.
- detalhe (/deputados/{id}): nomeCivil, sexo, dataNascimento, ufNascimento,
  municipioNascimento e ultimoStatus{situacao, condicaoEleitoral, data, ...}.

Apenas `id` e `nome` são obrigatórios; o payload completo (lista + detalhe) é
preservado em `deputados.payload_origem` para auditoria e remapeamento futuro.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.coletores import registro
from app.coletores.http import ClienteHttp, ErroColeta
from app.coletores.persistencia import upsert_com_hash, upsert_simples
from app.coletores.util import data_iso, hash_payload, inteiro, sha256_bytes, texto
from app.config import Settings
from app.models import Deputado, Filiacao, FonteImportacao, Mandato

logger = logging.getLogger(__name__)

ITENS_POR_PAGINA = 100  # máximo aceito pela API


@dataclass
class DeputadoNormalizado:
    deputado: dict[str, Any]
    id_legislatura: int | None
    sigla_uf: str | None
    sigla_partido: str | None
    uri_partido: str | None
    situacao: str | None
    condicao_eleitoral: str | None
    data_status: Any


def normalizar(item: dict[str, Any], detalhe: dict[str, Any] | None) -> DeputadoNormalizado:
    """Converte o payload oficial em colunas. Lança ValueError se inválido."""
    id_camara = inteiro(item.get("id"))
    nome = texto(item.get("nome"))
    if id_camara is None or nome is None:
        raise ValueError("Campos obrigatórios ausentes: 'id' e/ou 'nome'")
    detalhe = detalhe or {}
    status = detalhe.get("ultimoStatus") or {}
    payload = {"lista": item, "detalhe": detalhe or None}
    sexo = texto(detalhe.get("sexo"))
    return DeputadoNormalizado(
        deputado={
            "id_camara": id_camara,
            "nome": nome,
            "nome_civil": texto(detalhe.get("nomeCivil")),
            "sexo": sexo[:1] if sexo else None,
            "data_nascimento": data_iso(detalhe.get("dataNascimento")),
            "uf_nascimento": texto(detalhe.get("ufNascimento")),
            "municipio_nascimento": texto(detalhe.get("municipioNascimento")),
            "url_foto": texto(item.get("urlFoto")),
            "email": texto(item.get("email")),
            "hash_payload": hash_payload(payload),
            "payload_origem": payload,
        },
        id_legislatura=inteiro(item.get("idLegislatura")),
        sigla_uf=texto(item.get("siglaUf")),
        sigla_partido=texto(item.get("siglaPartido")),
        uri_partido=texto(item.get("uriPartido")),
        situacao=texto(status.get("situacao")),
        condicao_eleitoral=texto(status.get("condicaoEleitoral")),
        data_status=data_iso(status.get("data")),
    )


def _salvar_bruto(settings: Settings, fonte: FonteImportacao, paginas: list[Any]) -> None:
    conteudo = json.dumps(paginas, ensure_ascii=False, sort_keys=True).encode("utf-8")
    fonte.hash_sha256 = sha256_bytes(conteudo)
    fonte.tamanho_bytes = len(conteudo)
    destino = Path(settings.diretorio_dados_brutos) / "deputados"
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / f"deputados-{fonte.id}-{fonte.hash_sha256[:16]}.json"
    caminho.write_bytes(conteudo)
    fonte.caminho_arquivo_bruto = str(caminho)


def importar_deputados(
    session: Session,
    cliente: ClienteHttp,
    settings: Settings,
    id_legislatura: int | None = None,
    com_detalhes: bool = True,
) -> FonteImportacao:
    base = settings.camara_api_base_url.rstrip("/")
    url = f"{base}/deputados"
    params: dict[str, Any] = {"itens": ITENS_POR_PAGINA, "ordem": "ASC", "ordenarPor": "nome"}
    if id_legislatura is not None:
        params["idLegislatura"] = id_legislatura
    fonte = registro.iniciar(
        session, "deputados_api", url, {**params, "com_detalhes": com_detalhes}
    )
    paginas_brutas: list[Any] = []
    try:
        for url_pagina, corpo in cliente.paginar(url, params):
            paginas_brutas.append({"url": url_pagina, "corpo": corpo})
            dados = corpo.get("dados")
            if not isinstance(dados, list):
                raise ErroColeta(f"Resposta sem lista 'dados' em {url_pagina}")
            for item in dados:
                fonte.registros_lidos += 1
                _processar_item(session, cliente, base, fonte, item, com_detalhes)
            session.commit()
        _salvar_bruto(settings, fonte, paginas_brutas)
        fonte.metadados = {"paginas": len(paginas_brutas)}
        registro.finalizar(session, fonte)
    except Exception as exc:
        registro.falhar(session, fonte, exc)
        raise
    return fonte


def _processar_item(
    session: Session,
    cliente: ClienteHttp,
    base: str,
    fonte: FonteImportacao,
    item: dict[str, Any],
    com_detalhes: bool,
) -> None:
    referencia = f"deputado id={item.get('id')}"
    detalhe = None
    if com_detalhes and item.get("id") is not None:
        try:
            detalhe = cliente.get_json(f"{base}/deputados/{item['id']}").get("dados")
        except ErroColeta as exc:
            registro.registrar_erro(
                session, fonte, f"Detalhe indisponível: {exc}", referencia, item
            )
    try:
        norm = normalizar(item, detalhe)
    except ValueError as exc:
        registro.registrar_erro(session, fonte, str(exc), referencia, item)
        return

    linha = {**norm.deputado, "coletado_em": registro.agora(), "fonte_importacao_id": fonte.id}
    inseridos, atualizados, ids = upsert_com_hash(
        session, Deputado.__table__, [linha], ["id_camara"]
    )
    fonte.registros_inseridos += inseridos
    fonte.registros_atualizados += atualizados
    if not ids:
        fonte.registros_inalterados += 1
        return

    deputado_id = ids[norm.deputado["id_camara"]]
    if norm.id_legislatura is not None:
        upsert_simples(
            session,
            Mandato.__table__,
            [
                {
                    "deputado_id": deputado_id,
                    "id_legislatura": norm.id_legislatura,
                    "sigla_uf": norm.sigla_uf,
                    "situacao": norm.situacao,
                    "condicao_eleitoral": norm.condicao_eleitoral,
                }
            ],
            ["deputado_id", "id_legislatura"],
        )
        if norm.sigla_partido:
            upsert_simples(
                session,
                Filiacao.__table__,
                [
                    {
                        "deputado_id": deputado_id,
                        "id_legislatura": norm.id_legislatura,
                        "sigla_partido": norm.sigla_partido,
                        "uri_partido": norm.uri_partido,
                        "data_referencia": norm.data_status,
                    }
                ],
                ["deputado_id", "id_legislatura", "sigla_partido"],
            )
