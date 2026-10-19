# Fiscaliza Brasil

Plataforma web independente para acompanhar os gastos dos deputados federais brasileiros
a partir de dados oficiais da Câmara dos Deputados.

> **Princípios.** Só exibimos dados obtidos de fontes oficiais, com a origem preservada.
> Alertas são indicadores para revisão humana e **não** constituem acusação de
> irregularidade ou corrupção. Despesas da CEAP (Cota para o Exercício da Atividade
> Parlamentar) são sempre identificadas como tal e não se confundem com outros gastos.

## Estrutura

```
backend/    FastAPI, SQLAlchemy 2, Alembic, coletores e testes (pytest)
frontend/   Next.js (App Router) + TypeScript + Tailwind CSS
docker-compose.yml  PostgreSQL 16 + backend + frontend
```

## Início rápido (Docker Compose)

```bash
cp .env.example .env        # ajuste POSTGRES_PASSWORD e DATABASE_URL
docker compose up -d --build
```

- Frontend: http://localhost:3000 (status das fontes em `/fontes`)
- API: http://localhost:8000/api/v1/health · documentação em http://localhost:8000/docs

As migrations rodam automaticamente ao iniciar o backend (`alembic upgrade head`).

### Importações

```bash
docker compose exec backend python -m app.cli deputados                 # legislatura atual
docker compose exec backend python -m app.cli deputados --legislatura 57
docker compose exec backend python -m app.cli ceap --ano 2024
docker compose exec backend python -m app.cli ceap --ano 2024 --arquivo /app/data/Ano-2024.csv.zip
```

O comando imprime o resumo (lidos, inseridos, atualizados, inalterados, erros) e sai com
código `0` (sucesso/sem alteração), `2` (concluída com erros em registros) ou `1` (falha).
Consulte sempre `GET /api/v1/fontes/status` ou a tabela `fontes_importacao` para confirmar
o resultado de uma importação.

Atalhos equivalentes no `Makefile`: `make up`, `make importar-deputados`,
`make importar-ceap ANO=2024`, `make test`.

## Desenvolvimento sem Docker

```bash
# Backend (Python 3.12+)
cd backend
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/fiscaliza
alembic upgrade head
uvicorn app.main:app --reload

# Frontend (Node 22)
cd frontend
npm install
API_INTERNAL_URL=http://localhost:8000 npm run dev
```

## Testes

```bash
cd backend
ruff check . && ruff format --check .
# Testes de integração exigem um banco DESCARTÁVEL cujo nome contenha "test";
# o banco é recriado (downgrade/upgrade) e as tabelas são truncadas.
TEST_DATABASE_URL=postgresql+psycopg://usuario:senha@localhost:5432/fiscaliza_test pytest -q

cd ../frontend
npm test && npm run typecheck && npm run build
```

Sem `TEST_DATABASE_URL`, os testes de integração são ignorados (skip) e só os unitários rodam.

## API

| Método | Rota | Descrição |
|---|---|---|
| GET | `/api/v1/health` | Status da API e do banco (503 se o banco estiver indisponível) |
| GET | `/api/v1/fontes/status` | Última importação de cada fonte, contagens, hash e erro |

## Modelo de dados

| Tabela | Conteúdo | Chave de deduplicação |
|---|---|---|
| `fontes_importacao` | Cada execução de coleta: URL, parâmetros, status, SHA-256, tamanho, arquivo bruto, contagens, erro | — |
| `erros_importacao` | Registros rejeitados, com o payload original e a referência (linha/ID) | — |
| `deputados` | Cadastro (API v2) + `payload_origem` (lista + detalhe) e `hash_payload` | `id_camara` |
| `mandatos` | Deputado × legislatura, UF, situação, condição eleitoral | (`deputado_id`, `id_legislatura`) |
| `filiacoes` | Partido observado por legislatura (`data_referencia` = data do status na fonte) | (`deputado_id`, `id_legislatura`, `sigla_partido`) |
| `fornecedores` | CNPJ/CPF normalizado ou nome normalizado quando não há documento | `chave_origem` |
| `despesas` | Gastos com `tipo_gasto` (`CEAP` por ora), valores `NUMERIC(14,2)`, `data_emissao` `DATE`, payload original | `chave_origem` |
| `documentos` | Links de comprovantes (`urlDocumento`) | (`despesa_id`, `url`) |
| `alertas` | Indicadores para revisão (status `pendente`/`em_revisao`/`descartado`/`procedente`) | `chave_deduplicacao` |
| `revisoes_alertas` | Histórico das revisões humanas, com justificativa obrigatória | — |

Datas de calendário usam `DATE`; instantes (coleta, criação) usam `TIMESTAMPTZ` em UTC.

## Coleta: garantias

- **Idempotência:** `INSERT ... ON CONFLICT` pela chave de origem; a linha só é atualizada se o
  `hash_payload` mudou. Arquivo CEAP com o mesmo SHA-256 da última importação bem-sucedida do
  ano é marcado `sem_alteracao` sem reprocessar (use `--forcar` para reprocessar).
- **Retry:** backoff exponencial com jitter para 429/5xx e falhas de rede, respeitando
  `Retry-After`; erros 4xx definitivos não são repetidos.
- **Paginação segura:** segue `links[rel=next]` com limite de páginas, detecção de ciclo e
  recusa de links para outro host.
- **Proteções do arquivo CEAP:** limite de tamanho do download e do CSV descompactado, exige
  exatamente um CSV no zip, detecção UTF-8/Latin-1, validação do cabeçalho.
- **Rastreabilidade:** o arquivo bruto é salvo em `DIRETORIO_DADOS_BRUTOS` com o hash no nome;
  o payload de cada registro fica em JSONB.
- **Logs estruturados:** JSON em uma linha por evento (stdout).

### Chave de origem da CEAP

`ceap:doc:<ideDocumento>:<numParcela>:<numRessarcimento>:<numLote>` quando há `ideDocumento`;
caso contrário, `ceap:linha:<sha256 da linha>`. Linhas com chave repetida dentro do mesmo
arquivo são registradas em `erros_importacao` (não são descartadas silenciosamente).

## Campos oficiais e pendências de verificação

- **API v2 `/deputados`:** usados `id`, `nome`, `siglaPartido`, `uriPartido`, `siglaUf`,
  `idLegislatura`, `urlFoto`, `email`; detalhe `/deputados/{id}`: `nomeCivil`, `sexo`,
  `dataNascimento`, `ufNascimento`, `municipioNascimento`, `ultimoStatus`.
- **CEAP (`Ano-AAAA.csv.zip`, separador `;`):** colunas obrigatórias verificadas em tempo de
  execução: `txNomeParlamentar`, `ideCadastro`, `numAno`, `numMes`, `numSubCota`,
  `txtDescricao`, `txtFornecedor`, `txtCNPJCPF`, `vlrDocumento`, `vlrLiquido`, `ideDocumento`.
  Opcionais mapeadas: `sgUF`, `sgPartido`, `codLegislatura`, `numEspecificacaoSubCota`,
  `txtDescricaoEspecificacao`, `txtNumero`, `indTipoDocumento`, `datEmissao`, `vlrGlosa`,
  `vlrRestituicao`, `numParcela`, `txtPassageiro`, `txtTrecho`, `numLote`,
  `numRessarcimento`, `urlDocumento`.

⚠️ Na criação desta etapa, o ambiente de desenvolvimento não tinha acesso de rede a
`camara.leg.br`. Os nomes acima foram conferidos contra uma referência secundária
(pacote `serenata-toolbox`, que processa esses mesmos arquivos) e contra o formato
conhecido da API, **não** contra uma resposta ao vivo. Antes do primeiro uso em produção:

1. Rodar `python -m app.cli deputados --sem-detalhes` e conferir um `payload_origem`.
2. Baixar um `Ano-AAAA.csv.zip`, conferir o cabeçalho e a URL em `CEAP_ARQUIVO_URL_TEMPLATE`,
   e importar com `--arquivo`. Se faltar coluna obrigatória, a importação falha com a lista
   do cabeçalho encontrado.
3. Conferir o formato decimal dos valores (o parser aceita `1234.56`, `1234,56` e `1.234,56`).
