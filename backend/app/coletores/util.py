"""Funções puras de normalização, parsing e hash."""

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def sha256_bytes(dados: bytes) -> str:
    return hashlib.sha256(dados).hexdigest()


def hash_payload(payload: Any) -> str:
    """Hash estável de um payload JSON (chaves ordenadas, sem espaços)."""
    canonico = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return sha256_bytes(canonico.encode("utf-8"))


def texto(valor: Any) -> str | None:
    if valor is None:
        return None
    s = str(valor).strip()
    return s or None


def inteiro(valor: Any) -> int | None:
    s = texto(valor)
    if s is None:
        return None
    try:
        return int(Decimal(s.replace(",", ".")))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Inteiro inválido: {valor!r}") from None


def decimal_monetario(valor: Any) -> Decimal | None:
    """Converte texto monetário em Decimal com 2 casas.

    Aceita "1234.56", "1234,56" e "1.234,56". Nunca usa float.
    """
    s = texto(valor)
    if s is None:
        return None
    s = s.replace("R$", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return Decimal(s).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise ValueError(f"Valor monetário inválido: {valor!r}") from None


def data_iso(valor: Any) -> date | None:
    """Converte "AAAA-MM-DD", "AAAA-MM-DDTHH:MM:SS" ou "DD/MM/AAAA" em date."""
    s = texto(valor)
    if s is None:
        return None
    if re.fullmatch(r"\d{2}/\d{2}/\d{4}", s):
        return datetime.strptime(s, "%d/%m/%Y").date()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        raise ValueError(f"Data inválida: {valor!r}") from None


def somente_digitos(valor: Any) -> str | None:
    s = texto(valor)
    if s is None:
        return None
    digitos = re.sub(r"\D", "", s)
    return digitos or None


def normalizar_nome(valor: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", valor).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def classificar_documento(digitos: str | None) -> str:
    if digitos and len(digitos) == 14:
        return "CNPJ"
    if digitos and len(digitos) == 11:
        return "CPF"
    return "OUTRO"
