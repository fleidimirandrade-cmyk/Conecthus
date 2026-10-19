import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import __version__
from app.config import get_settings
from app.db import get_session
from app.models import FonteImportacao
from app.schemas import Health, StatusFonte, StatusFontes, UltimaImportacao

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1")
SessaoDep = Annotated[Session, Depends(get_session)]

FONTES = {
    "deputados_api": {
        "nome": "Deputados (API Dados Abertos da Câmara)",
        "descricao": (
            "Cadastro de deputados federais, legislatura, UF e partido informados pela API v2."
        ),
        "url": lambda s: f"{s.camara_api_base_url.rstrip('/')}/deputados",
    },
    "ceap_arquivo_anual": {
        "nome": "CEAP — arquivos anuais",
        "descricao": (
            "Despesas reembolsadas pela Cota para o Exercício da Atividade Parlamentar. "
            "Não inclui salários, verbas de gabinete nem outros gastos."
        ),
        "url": lambda s: s.ceap_arquivo_url_template,
    },
}


@router.get("/health", response_model=Health)
def health(response: Response, session: SessaoDep) -> Health:
    try:
        session.execute(text("SELECT 1"))
        banco = "ok"
    except Exception:
        logger.exception("health_banco_indisponivel")
        banco = "indisponivel"
        response.status_code = 503
    return Health(
        status="ok" if banco == "ok" else "degradado", banco_de_dados=banco, versao=__version__
    )


@router.get("/fontes/status", response_model=StatusFontes)
def status_fontes(session: SessaoDep) -> StatusFontes:
    settings = get_settings()
    fontes = []
    for tipo, info in FONTES.items():
        ultima = session.scalar(
            select(FonteImportacao)
            .where(FonteImportacao.tipo == tipo)
            .order_by(FonteImportacao.iniciado_em.desc(), FonteImportacao.id.desc())
            .limit(1)
        )
        ultimo_sucesso = session.scalar(
            select(func.max(FonteImportacao.finalizado_em)).where(
                FonteImportacao.tipo == tipo,
                FonteImportacao.status.in_(("sucesso", "parcial", "sem_alteracao")),
            )
        )
        fontes.append(
            StatusFonte(
                tipo=tipo,
                nome=info["nome"],
                descricao=info["descricao"],
                url_referencia=info["url"](settings),
                ultima_importacao=UltimaImportacao.model_validate(ultima, from_attributes=True)
                if ultima
                else None,
                ultima_importacao_bem_sucedida_em=ultimo_sucesso,
            )
        )
    return StatusFontes(gerado_em=datetime.now(UTC), fontes=fontes)
