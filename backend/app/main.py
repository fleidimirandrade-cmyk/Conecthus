from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api.routes import router
from app.config import get_settings
from app.logging_config import configurar_logs


def criar_app() -> FastAPI:
    settings = get_settings()
    configurar_logs(settings.log_level)
    app = FastAPI(
        title="Fiscaliza Brasil API",
        version=__version__,
        description="Dados públicos sobre gastos de deputados federais. "
        "Alertas são indicadores para revisão, não acusações.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_lista,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = criar_app()
