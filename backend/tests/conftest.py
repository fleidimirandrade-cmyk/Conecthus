import csv
import io
import os
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings
from app.models import Base

CABECALHO_CEAP = [
    "txNomeParlamentar", "cpf", "ideCadastro", "nuCarteiraParlamentar", "nuLegislatura",
    "sgUF", "sgPartido", "codLegislatura", "numSubCota", "txtDescricao",
    "numEspecificacaoSubCota", "txtDescricaoEspecificacao", "txtFornecedor", "txtCNPJCPF",
    "txtNumero", "indTipoDocumento", "datEmissao", "vlrDocumento", "vlrGlosa", "vlrLiquido",
    "numMes", "numAno", "numParcela", "txtPassageiro", "txtTrecho", "numLote",
    "numRessarcimento", "datPagamentoRestituicao", "vlrRestituicao", "nuDeputadoId",
    "ideDocumento", "urlDocumento",
]  # fmt: skip


def linha_ceap(**valores: str) -> dict[str, str]:
    """Linha sintética para testes (não representa nenhuma despesa real)."""
    base = {c: "" for c in CABECALHO_CEAP}
    base.update(
        {
            "txNomeParlamentar": "DEPUTADO TESTE",
            "ideCadastro": "1001",
            "sgUF": "DF",
            "sgPartido": "PTESTE",
            "codLegislatura": "57",
            "numSubCota": "3",
            "txtDescricao": "COMBUSTÍVEIS E LUBRIFICANTES.",
            "txtFornecedor": "POSTO EXEMPLO LTDA",
            "txtCNPJCPF": "00.000.000/0001-91",
            "txtNumero": "123",
            "indTipoDocumento": "0",
            "datEmissao": "2024-03-05T00:00:00",
            "vlrDocumento": "150.10",
            "vlrGlosa": "0",
            "vlrLiquido": "150.10",
            "numMes": "3",
            "numAno": "2024",
            "numParcela": "0",
            "numLote": "555",
            "numRessarcimento": "",
            "ideDocumento": "9000001",
            "urlDocumento": "https://exemplo.invalid/doc/9000001.pdf",
        }
    )
    base.update(valores)
    return base


def criar_zip_ceap(
    caminho: Path,
    linhas: list[dict[str, str]],
    cabecalho: list[str] | None = None,
    codificacao: str = "utf-8-sig",
) -> Path:
    buffer = io.StringIO()
    escritor = csv.DictWriter(
        buffer,
        fieldnames=cabecalho or CABECALHO_CEAP,
        delimiter=";",
        quoting=csv.QUOTE_ALL,
        extrasaction="ignore",
    )
    escritor.writeheader()
    escritor.writerows(linhas)
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("Ano-2024.csv", buffer.getvalue().encode(codificacao))
    return caminho


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://x@localhost/x"),
        camara_api_base_url="https://api.teste.invalid/api/v2",
        ceap_arquivo_url_template="https://arquivos.teste.invalid/cotas/Ano-{ano}.csv.zip",
        http_backoff_base_segundos=0.0,
        http_max_tentativas=3,
        diretorio_dados_brutos=str(tmp_path / "brutos"),
        ceap_tamanho_lote=2,
    )


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL não definida: testes de integração ignorados")
    # Proteção: os testes apagam dados, então só rodam em bancos cujo nome contém "test".
    if "test" not in url.rsplit("/", 1)[-1]:
        pytest.fail("TEST_DATABASE_URL deve apontar para um banco de testes (nome com 'test')")
    eng = create_engine(url)
    try:
        with eng.connect():
            pass
    except Exception as exc:  # pragma: no cover
        pytest.skip(f"PostgreSQL de testes indisponível: {exc}")

    from alembic.config import Config

    from alembic import command

    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    tabelas = ", ".join(t.name for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tabelas} RESTART IDENTITY CASCADE"))
    with sessionmaker(bind=engine, expire_on_commit=False)() as s:
        yield s
