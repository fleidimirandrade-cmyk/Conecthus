from datetime import datetime

from pydantic import BaseModel


class Health(BaseModel):
    status: str
    banco_de_dados: str
    versao: str


class UltimaImportacao(BaseModel):
    id: int
    status: str
    url: str
    iniciado_em: datetime
    finalizado_em: datetime | None
    hash_sha256: str | None
    tamanho_bytes: int | None
    registros_lidos: int
    registros_inseridos: int
    registros_atualizados: int
    registros_inalterados: int
    registros_com_erro: int
    mensagem_erro: str | None
    parametros: dict


class StatusFonte(BaseModel):
    tipo: str
    nome: str
    descricao: str
    url_referencia: str
    ultima_importacao: UltimaImportacao | None
    ultima_importacao_bem_sucedida_em: datetime | None


class StatusFontes(BaseModel):
    gerado_em: datetime
    fontes: list[StatusFonte]
