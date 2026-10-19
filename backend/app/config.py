from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuração lida de variáveis de ambiente (ver .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fiscaliza:fiscaliza@localhost:5432/fiscaliza"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    camara_api_base_url: str = "https://dadosabertos.camara.leg.br/api/v2"
    ceap_arquivo_url_template: str = "https://www.camara.leg.br/cotas/Ano-{ano}.csv.zip"

    http_timeout_segundos: float = 30.0
    http_max_tentativas: int = 5
    http_backoff_base_segundos: float = 1.0
    http_backoff_max_segundos: float = 30.0

    paginacao_max_paginas: int = 200
    ceap_tamanho_max_bytes: int = 500 * 1024 * 1024
    ceap_tamanho_descompactado_max_bytes: int = 2 * 1024 * 1024 * 1024
    ceap_tamanho_lote: int = 1000

    diretorio_dados_brutos: str = "data/brutos"

    @property
    def cors_origins_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
