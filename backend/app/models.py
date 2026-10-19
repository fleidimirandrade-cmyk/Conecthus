"""Modelo de dados do Fiscaliza Brasil.

Convenções:
- Valores monetários: NUMERIC(14, 2) mapeado para Decimal (nunca float).
- Datas de calendário (emissão, nascimento): DATE. Instantes (coleta, criação): TIMESTAMPTZ.
- Registros vindos de fontes externas guardam o identificador/chave de origem
  (único) para deduplicação e o payload original em JSONB.
- `despesas.tipo_gasto` distingue a Cota para o Exercício da Atividade
  Parlamentar (CEAP) de outros tipos de gasto que venham a ser importados.
- Alertas são indicadores para revisão humana; não constituem acusação.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

Dinheiro = Numeric(14, 2)

TIPOS_FONTE = ("deputados_api", "ceap_arquivo_anual")
STATUS_IMPORTACAO = ("em_andamento", "sucesso", "parcial", "falha", "sem_alteracao")
TIPOS_GASTO = ("CEAP",)
STATUS_ALERTA = ("pendente", "em_revisao", "descartado", "procedente")
SEVERIDADES_ALERTA = ("informativo", "atencao")


def _in(coluna: str, valores: tuple[str, ...]) -> str:
    return f"{coluna} IN ({', '.join(repr(v) for v in valores)})"


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class FonteImportacao(Base):
    """Uma execução de coleta/importação de uma fonte oficial."""

    __tablename__ = "fontes_importacao"
    __table_args__ = (
        CheckConstraint(_in("tipo", TIPOS_FONTE), name="tipo_valido"),
        CheckConstraint(_in("status", STATUS_IMPORTACAO), name="status_valido"),
        Index("ix_fontes_importacao_tipo_iniciado_em", "tipo", "iniciado_em"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tipo: Mapped[str] = mapped_column(String(40), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    parametros: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="em_andamento")
    iniciado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finalizado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hash_sha256: Mapped[str | None] = mapped_column(String(64))
    tamanho_bytes: Mapped[int | None] = mapped_column(BigInteger)
    caminho_arquivo_bruto: Mapped[str | None] = mapped_column(Text)
    metadados: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    registros_lidos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_inseridos: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_atualizados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_inalterados: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    registros_com_erro: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mensagem_erro: Mapped[str | None] = mapped_column(Text)

    erros: Mapped[list["ErroImportacao"]] = relationship(back_populates="fonte")


class ErroImportacao(Base):
    """Registro individual que não pôde ser importado, com o conteúdo original."""

    __tablename__ = "erros_importacao"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    fonte_importacao_id: Mapped[int] = mapped_column(
        ForeignKey("fontes_importacao.id", ondelete="CASCADE"), index=True, nullable=False
    )
    referencia: Mapped[str | None] = mapped_column(Text)  # ex.: "linha 1234" ou URL
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    payload_origem: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    fonte: Mapped[FonteImportacao] = relationship(back_populates="erros")


class Deputado(TimestampMixin, Base):
    __tablename__ = "deputados"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    id_camara: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    nome_civil: Mapped[str | None] = mapped_column(Text)
    sexo: Mapped[str | None] = mapped_column(String(1))
    data_nascimento: Mapped[date | None] = mapped_column(Date)
    uf_nascimento: Mapped[str | None] = mapped_column(String(2))
    municipio_nascimento: Mapped[str | None] = mapped_column(Text)
    url_foto: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    hash_payload: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_origem: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fonte_importacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("fontes_importacao.id", ondelete="SET NULL")
    )

    mandatos: Mapped[list["Mandato"]] = relationship(back_populates="deputado")
    filiacoes: Mapped[list["Filiacao"]] = relationship(back_populates="deputado")


class Mandato(TimestampMixin, Base):
    """Exercício do deputado em uma legislatura (fonte: API da Câmara)."""

    __tablename__ = "mandatos"
    __table_args__ = (UniqueConstraint("deputado_id", "id_legislatura"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deputado_id: Mapped[int] = mapped_column(
        ForeignKey("deputados.id", ondelete="CASCADE"), nullable=False
    )
    id_legislatura: Mapped[int] = mapped_column(Integer, nullable=False)
    sigla_uf: Mapped[str | None] = mapped_column(String(2))
    situacao: Mapped[str | None] = mapped_column(Text)
    condicao_eleitoral: Mapped[str | None] = mapped_column(Text)
    data_inicio: Mapped[date | None] = mapped_column(Date)
    data_fim: Mapped[date | None] = mapped_column(Date)

    deputado: Mapped[Deputado] = relationship(back_populates="mandatos")


class Filiacao(TimestampMixin, Base):
    """Partido observado para o deputado em uma legislatura.

    `data_referencia` é a data do status informado pela fonte, não
    necessariamente a data de filiação partidária oficial.
    """

    __tablename__ = "filiacoes"
    __table_args__ = (UniqueConstraint("deputado_id", "id_legislatura", "sigla_partido"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    deputado_id: Mapped[int] = mapped_column(
        ForeignKey("deputados.id", ondelete="CASCADE"), nullable=False
    )
    id_legislatura: Mapped[int] = mapped_column(Integer, nullable=False)
    sigla_partido: Mapped[str] = mapped_column(String(30), nullable=False)
    uri_partido: Mapped[str | None] = mapped_column(Text)
    data_referencia: Mapped[date | None] = mapped_column(Date)

    deputado: Mapped[Deputado] = relationship(back_populates="filiacoes")


class Fornecedor(TimestampMixin, Base):
    __tablename__ = "fornecedores"
    __table_args__ = (
        CheckConstraint("tipo_documento IN ('CNPJ', 'CPF', 'OUTRO')", name="tipo_documento_valido"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Documento normalizado (apenas dígitos) ou "nome:<nome normalizado>" quando ausente.
    chave_origem: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    cnpj_cpf: Mapped[str | None] = mapped_column(String(14), index=True)
    tipo_documento: Mapped[str] = mapped_column(String(5), nullable=False)
    nome: Mapped[str] = mapped_column(Text, nullable=False)


class Despesa(TimestampMixin, Base):
    __tablename__ = "despesas"
    __table_args__ = (
        CheckConstraint(_in("tipo_gasto", TIPOS_GASTO), name="tipo_gasto_valido"),
        CheckConstraint("mes BETWEEN 1 AND 12", name="mes_valido"),
        Index("ix_despesas_deputado_ano_mes", "deputado_id", "ano", "mes"),
        Index("ix_despesas_id_camara_deputado", "id_camara_deputado"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chave_origem: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    tipo_gasto: Mapped[str] = mapped_column(String(20), nullable=False)
    deputado_id: Mapped[int | None] = mapped_column(
        ForeignKey("deputados.id", ondelete="SET NULL"), index=True
    )
    id_camara_deputado: Mapped[int | None] = mapped_column(Integer)
    nome_parlamentar: Mapped[str | None] = mapped_column(Text)
    sigla_uf: Mapped[str | None] = mapped_column(String(2))
    sigla_partido: Mapped[str | None] = mapped_column(String(30))
    id_legislatura: Mapped[int | None] = mapped_column(Integer)
    ano: Mapped[int] = mapped_column(Integer, nullable=False)
    mes: Mapped[int] = mapped_column(Integer, nullable=False)
    numero_subcota: Mapped[int | None] = mapped_column(Integer)
    descricao_subcota: Mapped[str | None] = mapped_column(Text)
    numero_especificacao_subcota: Mapped[int | None] = mapped_column(Integer)
    descricao_especificacao_subcota: Mapped[str | None] = mapped_column(Text)
    fornecedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("fornecedores.id", ondelete="SET NULL"), index=True
    )
    numero_documento: Mapped[str | None] = mapped_column(Text)
    tipo_documento: Mapped[int | None] = mapped_column(Integer)
    data_emissao: Mapped[date | None] = mapped_column(Date)
    valor_documento: Mapped[Decimal | None] = mapped_column(Dinheiro)
    valor_glosa: Mapped[Decimal | None] = mapped_column(Dinheiro)
    valor_liquido: Mapped[Decimal | None] = mapped_column(Dinheiro)
    valor_restituicao: Mapped[Decimal | None] = mapped_column(Dinheiro)
    numero_parcela: Mapped[int | None] = mapped_column(Integer)
    passageiro: Mapped[str | None] = mapped_column(Text)
    trecho: Mapped[str | None] = mapped_column(Text)
    numero_lote: Mapped[str | None] = mapped_column(Text)
    numero_ressarcimento: Mapped[str | None] = mapped_column(Text)
    id_documento_origem: Mapped[str | None] = mapped_column(Text)
    hash_payload: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_origem: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    coletado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fonte_importacao_id: Mapped[int | None] = mapped_column(
        ForeignKey("fontes_importacao.id", ondelete="SET NULL")
    )

    documentos: Mapped[list["Documento"]] = relationship(back_populates="despesa")


class Documento(TimestampMixin, Base):
    """Comprovante associado a uma despesa (ex.: link para nota fiscal digitalizada)."""

    __tablename__ = "documentos"
    __table_args__ = (UniqueConstraint("despesa_id", "url"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    despesa_id: Mapped[int] = mapped_column(
        ForeignKey("despesas.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    id_documento_origem: Mapped[str | None] = mapped_column(Text)

    despesa: Mapped[Despesa] = relationship(back_populates="documentos")


class Alerta(TimestampMixin, Base):
    """Indicador automático que pede revisão humana. Não é acusação nem conclusão."""

    __tablename__ = "alertas"
    __table_args__ = (
        CheckConstraint(_in("status", STATUS_ALERTA), name="status_valido"),
        CheckConstraint(_in("severidade", SEVERIDADES_ALERTA), name="severidade_valida"),
        UniqueConstraint("chave_deduplicacao"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    chave_deduplicacao: Mapped[str] = mapped_column(Text, nullable=False)
    regra: Mapped[str] = mapped_column(String(80), nullable=False)
    versao_regra: Mapped[str] = mapped_column(String(20), nullable=False)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    severidade: Mapped[str] = mapped_column(String(20), nullable=False, default="informativo")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pendente")
    evidencias: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    despesa_id: Mapped[int | None] = mapped_column(
        ForeignKey("despesas.id", ondelete="SET NULL"), index=True
    )
    deputado_id: Mapped[int | None] = mapped_column(
        ForeignKey("deputados.id", ondelete="SET NULL"), index=True
    )

    revisoes: Mapped[list["RevisaoAlerta"]] = relationship(back_populates="alerta")


class RevisaoAlerta(Base):
    """Histórico (somente inserção) das revisões humanas de um alerta."""

    __tablename__ = "revisoes_alertas"
    __table_args__ = (
        CheckConstraint(_in("status_novo", STATUS_ALERTA), name="status_novo_valido"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    alerta_id: Mapped[int] = mapped_column(
        ForeignKey("alertas.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status_anterior: Mapped[str | None] = mapped_column(String(20))
    status_novo: Mapped[str] = mapped_column(String(20), nullable=False)
    revisor: Mapped[str] = mapped_column(Text, nullable=False)
    justificativa: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    alerta: Mapped[Alerta] = relationship(back_populates="revisoes")
