"""Upserts idempotentes no PostgreSQL (INSERT ... ON CONFLICT)."""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Table, func, literal_column, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session


def upsert_com_hash(
    session: Session,
    tabela: Table,
    linhas: Sequence[dict[str, Any]],
    colunas_conflito: Sequence[str],
    coluna_hash: str = "hash_payload",
) -> tuple[int, int, dict[Any, int]]:
    """Insere ou atualiza linhas; só atualiza quando o hash do payload mudou.

    Retorna (inseridos, atualizados, {chave_conflito: id}) — o mapa contém apenas
    as linhas inseridas/atualizadas. Linhas idênticas não são tocadas.
    """
    if not linhas:
        return 0, 0, {}
    stmt = insert(tabela).values(list(linhas))
    colunas_atualizar = {
        c: stmt.excluded[c]
        for c in linhas[0]
        if c not in colunas_conflito and c not in ("id", "criado_em")
    }
    if "atualizado_em" in tabela.c:
        colunas_atualizar["atualizado_em"] = func.now()
    stmt = stmt.on_conflict_do_update(
        index_elements=list(colunas_conflito),
        set_=colunas_atualizar,
        where=tabela.c[coluna_hash].is_distinct_from(stmt.excluded[coluna_hash]),
    ).returning(
        tabela.c.id,
        *[tabela.c[c] for c in colunas_conflito],
        literal_column("(xmax = 0)").label("inserido"),
    )
    inseridos = atualizados = 0
    ids: dict[Any, int] = {}
    for linha in session.execute(stmt):
        chave = linha[1] if len(colunas_conflito) == 1 else tuple(linha[1:-1])
        ids[chave] = linha.id
        if linha.inserido:
            inseridos += 1
        else:
            atualizados += 1
    return inseridos, atualizados, ids


def upsert_simples(
    session: Session,
    tabela: Table,
    linhas: Sequence[dict[str, Any]],
    colunas_conflito: Sequence[str],
    atualizar: bool = True,
) -> None:
    """Upsert sem contagem: atualiza as demais colunas (ou ignora, se atualizar=False)."""
    if not linhas:
        return
    stmt = insert(tabela).values(list(linhas))
    colunas_atualizar = {
        c: stmt.excluded[c] for c in linhas[0] if c not in colunas_conflito and c != "id"
    }
    if atualizar and colunas_atualizar:
        if "atualizado_em" in tabela.c:
            colunas_atualizar["atualizado_em"] = func.now()
        stmt = stmt.on_conflict_do_update(
            index_elements=list(colunas_conflito), set_=colunas_atualizar
        )
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=list(colunas_conflito))
    session.execute(stmt)


def mapear_ids(session: Session, tabela: Table, coluna: str, valores: set[Any]) -> dict[Any, int]:
    if not valores:
        return {}
    consulta = select(tabela.c[coluna], tabela.c.id).where(tabela.c[coluna].in_(valores))
    return {chave: id_ for chave, id_ in session.execute(consulta)}
