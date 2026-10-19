"""Ciclo de vida de uma execução de importação (tabela fontes_importacao)."""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models import ErroImportacao, FonteImportacao

logger = logging.getLogger(__name__)

MAX_ERROS_REGISTRADOS = 1000


def agora() -> datetime:
    return datetime.now(UTC)


def iniciar(session: Session, tipo: str, url: str, parametros: dict[str, Any]) -> FonteImportacao:
    fonte = FonteImportacao(tipo=tipo, url=url, parametros=parametros, status="em_andamento")
    session.add(fonte)
    session.commit()
    logger.info("importacao_iniciada", extra={"fonte_id": fonte.id, "tipo": tipo, "url": url})
    return fonte


def registrar_erro(
    session: Session,
    fonte: FonteImportacao,
    mensagem: str,
    referencia: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    fonte.registros_com_erro += 1
    if fonte.registros_com_erro <= MAX_ERROS_REGISTRADOS:
        session.add(
            ErroImportacao(
                fonte_importacao_id=fonte.id,
                referencia=referencia,
                mensagem=mensagem,
                payload_origem=payload,
            )
        )
    logger.warning(
        "registro_com_erro",
        extra={"fonte_id": fonte.id, "referencia": referencia, "erro": mensagem},
    )


def finalizar(session: Session, fonte: FonteImportacao, status: str | None = None) -> None:
    if status is None:
        status = "parcial" if fonte.registros_com_erro else "sucesso"
    fonte.status = status
    fonte.finalizado_em = agora()
    session.commit()
    logger.info(
        "importacao_finalizada",
        extra={
            "fonte_id": fonte.id,
            "tipo": fonte.tipo,
            "status": status,
            "lidos": fonte.registros_lidos,
            "inseridos": fonte.registros_inseridos,
            "atualizados": fonte.registros_atualizados,
            "inalterados": fonte.registros_inalterados,
            "com_erro": fonte.registros_com_erro,
        },
    )


def falhar(session: Session, fonte: FonteImportacao, erro: BaseException) -> None:
    session.rollback()
    fonte = session.merge(fonte)
    fonte.status = "falha"
    fonte.mensagem_erro = f"{type(erro).__name__}: {erro}"[:4000]
    fonte.finalizado_em = agora()
    session.commit()
    logger.error(
        "importacao_falhou",
        extra={"fonte_id": fonte.id, "tipo": fonte.tipo, "erro": fonte.mensagem_erro},
    )
