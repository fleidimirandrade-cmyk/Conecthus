"""Logs estruturados em JSON (uma linha por evento), sem dependências externas."""

import json
import logging
import sys
from datetime import UTC, datetime

_ATRIBUTOS_PADRAO = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        evento = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        for chave, valor in record.__dict__.items():
            if chave not in _ATRIBUTOS_PADRAO and not chave.startswith("_"):
                evento[chave] = valor
        if record.exc_info:
            evento["excecao"] = self.formatException(record.exc_info)
        return json.dumps(evento, ensure_ascii=False, default=str)


def configurar_logs(nivel: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    raiz = logging.getLogger()
    raiz.handlers[:] = [handler]
    raiz.setLevel(nivel.upper())
