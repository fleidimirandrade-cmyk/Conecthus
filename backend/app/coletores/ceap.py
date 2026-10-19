"""Importação dos arquivos anuais da CEAP (Cota para o Exercício da Atividade Parlamentar).

Fonte: arquivo `Ano-AAAA.csv.zip` publicado pela Câmara (URL configurável em
CEAP_ARQUIVO_URL_TEMPLATE), CSV separado por ';'.

ATENÇÃO: os nomes de colunas abaixo devem ser conferidos contra o cabeçalho do
arquivo oficial antes de cada nova safra. O importador verifica o cabeçalho em
tempo de execução e falha explicitamente se uma coluna obrigatória estiver
ausente; colunas extras são preservadas no payload de origem de cada linha.
"""

import codecs
import csv
import hashlib
import io
import logging
import os
import shutil
import tempfile
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.coletores import registro
from app.coletores.http import ClienteHttp, ErroColeta
from app.coletores.persistencia import mapear_ids, upsert_com_hash, upsert_simples
from app.coletores.util import (
    classificar_documento,
    data_iso,
    decimal_monetario,
    hash_payload,
    inteiro,
    normalizar_nome,
    somente_digitos,
    texto,
)
from app.config import Settings
from app.models import Deputado, Despesa, Documento, FonteImportacao, Fornecedor

logger = logging.getLogger(__name__)

COLUNAS_OBRIGATORIAS = frozenset(
    {
        "txNomeParlamentar",
        "ideCadastro",
        "numAno",
        "numMes",
        "numSubCota",
        "txtDescricao",
        "txtFornecedor",
        "txtCNPJCPF",
        "vlrDocumento",
        "vlrLiquido",
        "ideDocumento",
    }
)


class ErroFormatoCeap(ErroColeta):
    """O arquivo não tem o formato esperado (cabeçalho, zip, codificação)."""


def validar_cabecalho(cabecalho: list[str] | None) -> None:
    ausentes = COLUNAS_OBRIGATORIAS - set(cabecalho or [])
    if ausentes:
        raise ErroFormatoCeap(
            f"Colunas obrigatórias ausentes no CSV da CEAP: {sorted(ausentes)}. "
            f"Cabeçalho encontrado: {cabecalho}"
        )


def chave_origem(linha: dict[str, str]) -> str:
    """Chave natural da despesa.

    `ideDocumento` identifica o documento, mas um mesmo documento pode aparecer
    em várias linhas (parcelas, ressarcimentos, lotes). Sem `ideDocumento`
    válido, usa o hash do conteúdo da linha.
    """
    id_doc = texto(linha.get("ideDocumento"))
    if id_doc and id_doc != "0":
        partes = [
            id_doc,
            texto(linha.get("numParcela")) or "",
            texto(linha.get("numRessarcimento")) or "",
            texto(linha.get("numLote")) or "",
        ]
        return "ceap:doc:" + ":".join(partes)
    return "ceap:linha:" + hash_payload(linha)


def chave_fornecedor(linha: dict[str, str]) -> tuple[str, dict[str, Any]] | None:
    nome = texto(linha.get("txtFornecedor"))
    digitos = somente_digitos(linha.get("txtCNPJCPF"))
    if digitos:
        chave = digitos
    elif nome:
        chave = "nome:" + normalizar_nome(nome)
    else:
        return None
    return chave, {
        "chave_origem": chave,
        "cnpj_cpf": digitos if digitos and len(digitos) <= 14 else None,
        "tipo_documento": classificar_documento(digitos),
        "nome": nome or "(sem nome na fonte)",
    }


def normalizar_linha(linha: dict[str, str]) -> dict[str, Any]:
    """Converte uma linha do CSV em colunas de `despesas`. Lança ValueError se inválida."""
    ano = inteiro(linha.get("numAno"))
    mes = inteiro(linha.get("numMes"))
    if ano is None or mes is None:
        raise ValueError("numAno/numMes ausentes")
    if not 1 <= mes <= 12:
        raise ValueError(f"numMes fora do intervalo: {mes}")
    uf = texto(linha.get("sgUF"))
    return {
        "chave_origem": chave_origem(linha),
        "tipo_gasto": "CEAP",
        "id_camara_deputado": inteiro(linha.get("ideCadastro")),
        "nome_parlamentar": texto(linha.get("txNomeParlamentar")),
        "sigla_uf": uf if uf and len(uf) == 2 else None,
        "sigla_partido": texto(linha.get("sgPartido")),
        "id_legislatura": inteiro(linha.get("codLegislatura")),
        "ano": ano,
        "mes": mes,
        "numero_subcota": inteiro(linha.get("numSubCota")),
        "descricao_subcota": texto(linha.get("txtDescricao")),
        "numero_especificacao_subcota": inteiro(linha.get("numEspecificacaoSubCota")),
        "descricao_especificacao_subcota": texto(linha.get("txtDescricaoEspecificacao")),
        "numero_documento": texto(linha.get("txtNumero")),
        "tipo_documento": inteiro(linha.get("indTipoDocumento")),
        "data_emissao": data_iso(linha.get("datEmissao")),
        "valor_documento": decimal_monetario(linha.get("vlrDocumento")),
        "valor_glosa": decimal_monetario(linha.get("vlrGlosa")),
        "valor_liquido": decimal_monetario(linha.get("vlrLiquido")),
        "valor_restituicao": decimal_monetario(linha.get("vlrRestituicao")),
        "numero_parcela": inteiro(linha.get("numParcela")),
        "passageiro": texto(linha.get("txtPassageiro")),
        "trecho": texto(linha.get("txtTrecho")),
        "numero_lote": texto(linha.get("numLote")),
        "numero_ressarcimento": texto(linha.get("numRessarcimento")),
        "id_documento_origem": texto(linha.get("ideDocumento")),
        "hash_payload": hash_payload(linha),
        "payload_origem": linha,
    }


def _detectar_codificacao(amostra: bytes) -> str:
    try:
        codecs.getincrementaldecoder("utf-8")().decode(amostra, final=False)
        return "utf-8-sig"
    except UnicodeDecodeError:
        return "latin-1"


def ler_csv_zip(caminho: Path, settings: Settings) -> Iterator[tuple[int, dict[str, str]]]:
    """Itera (número da linha, linha) do CSV contido no zip, com proteções de tamanho."""
    try:
        arquivo_zip = zipfile.ZipFile(caminho)
    except zipfile.BadZipFile as exc:
        raise ErroFormatoCeap(f"Arquivo não é um zip válido: {caminho}") from exc
    with arquivo_zip:
        membros = [m for m in arquivo_zip.infolist() if m.filename.lower().endswith(".csv")]
        if len(membros) != 1:
            raise ErroFormatoCeap(f"Esperado 1 CSV no zip, encontrados {len(membros)}")
        membro = membros[0]
        if membro.file_size > settings.ceap_tamanho_descompactado_max_bytes:
            raise ErroFormatoCeap(f"CSV descompactado excede o limite: {membro.file_size} bytes")
        with arquivo_zip.open(membro) as bruto:
            amostra = bruto.read(1024 * 1024)
        codificacao = _detectar_codificacao(amostra)
        with arquivo_zip.open(membro) as bruto:
            leitor_texto = io.TextIOWrapper(bruto, encoding=codificacao, newline="")
            leitor = csv.DictReader(leitor_texto, delimiter=";", quotechar='"')
            validar_cabecalho(leitor.fieldnames)
            for linha in leitor:
                # Chaves None surgem quando a linha tem mais campos que o cabeçalho.
                extras = linha.pop(None, None)  # type: ignore[call-overload]
                if extras:
                    linha["__campos_excedentes__"] = extras  # type: ignore[assignment]
                yield leitor.line_num, linha


def _sha256_arquivo(caminho: Path) -> tuple[str, int]:
    h = hashlib.sha256()
    tamanho = 0
    with caminho.open("rb") as f:
        while bloco := f.read(1024 * 1024):
            h.update(bloco)
            tamanho += len(bloco)
    return h.hexdigest(), tamanho


def _hash_ultima_importacao(session: Session, ano: int) -> str | None:
    consulta = (
        select(FonteImportacao.hash_sha256)
        .where(
            FonteImportacao.tipo == "ceap_arquivo_anual",
            FonteImportacao.status.in_(("sucesso", "parcial", "sem_alteracao")),
            FonteImportacao.parametros["ano"].astext == str(ano),
        )
        .order_by(FonteImportacao.iniciado_em.desc())
        .limit(1)
    )
    return session.scalar(consulta)


def _obter_arquivo(
    cliente: ClienteHttp | None,
    settings: Settings,
    url: str,
    arquivo_local: Path | None,
    fonte: FonteImportacao,
) -> Path:
    destino_dir = Path(settings.diretorio_dados_brutos) / "ceap"
    destino_dir.mkdir(parents=True, exist_ok=True)
    descritor, nome_temporario = tempfile.mkstemp(dir=destino_dir, suffix=".parcial")
    os.close(descritor)
    temporario = Path(nome_temporario)
    try:
        if arquivo_local is not None:
            shutil.copyfile(arquivo_local, temporario)
            fonte.metadados = {"arquivo_local": str(arquivo_local)}
        else:
            assert cliente is not None
            fonte.metadados = cliente.baixar_arquivo(
                url, lambda: temporario.open("wb"), settings.ceap_tamanho_max_bytes
            )
        sha, tamanho = _sha256_arquivo(temporario)
        fonte.hash_sha256, fonte.tamanho_bytes = sha, tamanho
        final = destino_dir / f"{Path(url).name.removesuffix('.zip')}-{sha[:16]}.zip"
        temporario.replace(final)
    finally:
        temporario.unlink(missing_ok=True)
    fonte.caminho_arquivo_bruto = str(final)
    return final


def importar_ceap(
    session: Session,
    cliente: ClienteHttp | None,
    settings: Settings,
    ano: int,
    arquivo_local: Path | None = None,
    forcar: bool = False,
) -> FonteImportacao:
    url = settings.ceap_arquivo_url_template.format(ano=ano)
    fonte = registro.iniciar(
        session,
        "ceap_arquivo_anual",
        url,
        {"ano": ano, "arquivo_local": str(arquivo_local) if arquivo_local else None},
    )
    try:
        caminho = _obter_arquivo(cliente, settings, url, arquivo_local, fonte)
        anterior = _hash_ultima_importacao(session, ano)
        if anterior == fonte.hash_sha256 and not forcar:
            logger.info("ceap_sem_alteracao", extra={"ano": ano, "hash": fonte.hash_sha256})
            registro.finalizar(session, fonte, "sem_alteracao")
            return fonte
        _importar_linhas(session, settings, fonte, caminho)
        registro.finalizar(session, fonte)
    except Exception as exc:
        registro.falhar(session, fonte, exc)
        raise
    return fonte


def _importar_linhas(
    session: Session, settings: Settings, fonte: FonteImportacao, caminho: Path
) -> None:
    vistas: set[str] = set()
    lote: list[tuple[dict[str, Any], dict[str, Any] | None, str | None]] = []
    for numero_linha, linha in ler_csv_zip(caminho, settings):
        fonte.registros_lidos += 1
        referencia = f"linha {numero_linha}"
        try:
            despesa = normalizar_linha(linha)
        except ValueError as exc:
            registro.registrar_erro(session, fonte, str(exc), referencia, linha)
            continue
        if despesa["chave_origem"] in vistas:
            registro.registrar_erro(
                session,
                fonte,
                f"Chave de origem repetida no arquivo: {despesa['chave_origem']}",
                referencia,
                linha,
            )
            continue
        vistas.add(despesa["chave_origem"])
        fornecedor = chave_fornecedor(linha)
        url_doc = texto(linha.get("urlDocumento"))
        lote.append((despesa, fornecedor[1] if fornecedor else None, url_doc))
        if len(lote) >= settings.ceap_tamanho_lote:
            _gravar_lote(session, fonte, lote)
            lote = []
    _gravar_lote(session, fonte, lote)


def _gravar_lote(
    session: Session,
    fonte: FonteImportacao,
    lote: list[tuple[dict[str, Any], dict[str, Any] | None, str | None]],
) -> None:
    if not lote:
        return
    fornecedores = {f["chave_origem"]: f for _, f, _ in lote if f}
    upsert_simples(
        session,
        Fornecedor.__table__,
        list(fornecedores.values()),
        ["chave_origem"],
        atualizar=False,
    )
    ids_fornecedor = mapear_ids(session, Fornecedor.__table__, "chave_origem", set(fornecedores))
    ids_deputado = mapear_ids(
        session,
        Deputado.__table__,
        "id_camara",
        {d["id_camara_deputado"] for d, _, _ in lote if d["id_camara_deputado"] is not None},
    )
    coletado_em = registro.agora()
    linhas = [
        {
            **despesa,
            "fornecedor_id": ids_fornecedor.get(forn["chave_origem"]) if forn else None,
            "deputado_id": ids_deputado.get(despesa["id_camara_deputado"]),
            "coletado_em": coletado_em,
            "fonte_importacao_id": fonte.id,
        }
        for despesa, forn, _ in lote
    ]
    inseridos, atualizados, ids = upsert_com_hash(
        session, Despesa.__table__, linhas, ["chave_origem"]
    )
    fonte.registros_inseridos += inseridos
    fonte.registros_atualizados += atualizados
    fonte.registros_inalterados += len(lote) - inseridos - atualizados

    documentos = [
        {
            "despesa_id": ids[despesa["chave_origem"]],
            "url": url_doc,
            "id_documento_origem": despesa["id_documento_origem"],
        }
        for despesa, _, url_doc in lote
        if url_doc and despesa["chave_origem"] in ids
    ]
    upsert_simples(session, Documento.__table__, documentos, ["despesa_id", "url"], atualizar=False)
    session.commit()
