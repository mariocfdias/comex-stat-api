# 03 - Arquitetura da Nova Plataforma de Dados

## Visao Geral

Este documento descreve a arquitetura-alvo para a plataforma de dados que substituira a aplicacao NestJS monolitica atual. A nova plataforma segue o paradigma **data lakehouse**, com camadas bem definidas de armazenamento e processamento, orquestradas por ferramentas especializadas.

---

## Componentes da Plataforma

### 1. Apache Airflow - Orquestracao

Substitui os decoradores `@Cron` do NestJS (ex: `ScmSchedulerService` com `@Cron(CronExpression.EVERY_DAY_AT_2AM)`) e as chamadas on-demand que hoje disparam consultas a APIs externas.

**Responsabilidades:**
- Agendamento de todos os pipelines de ingestao (ComexStat, RDE, SCM, SIGMINE)
- Gerenciamento de dependencias entre tarefas (ex: bronze deve completar antes de silver)
- Politicas de retry com backoff exponencial (hoje implementadas manualmente em `ScmCsvService.downloadAndExtractData()`)
- Monitoramento via UI web com logs centralizados
- Alertas em caso de falha

### 2. MinIO - Object Storage (Data Lakehouse)

Substitui o armazenamento em sistema de arquivos local (ex: `data/scm/extracted/`) e os arquivos estaticos em `static/`.

**Responsabilidades:**
- Armazenamento de dados brutos (JSON, CSV, shapefiles) na camada Bronze
- Armazenamento de dados processados em Parquet nas camadas Silver e Gold
- Versionamento de objetos para auditoria e replay
- Particionamento por data de ingestao

### 3. Apache Spark / Pandas - Processamento de Dados

Substitui a logica de processamento em memoria do NestJS (ex: `ComexstatService` com agregacoes em JavaScript, `ScmCsvService` com parsing de CSV linha a linha).

**Responsabilidades:**
- Parsing de CSVs delimitados por ponto-e-virgula (SCM)
- Agregacoes pesadas do ComexStat (summary, timeseries, ranking de estados)
- Conversao de shapefiles para GeoJSON (SIGMINE)
- Filtragem geografica (bounding box do Ceara)

> **Nota:** Pandas e suficiente para datasets menores (RDE, SIGMINE). Spark e recomendado para ComexStat (combinatorica de estados x paises x produtos) e SCM (centenas de milhares de registros).

### 4. dbt (Data Build Tool) - Transformacoes SQL

Substitui as agregacoes em JavaScript feitas em memoria nos metodos do `ComexstatService` (ex: `getSummaryData()`, `getStatesRanking()`).

**Responsabilidades:**
- Transformacoes SQL versionadas sobre a camada Gold
- Pre-computacao de todas as formas de resposta da API (9 endpoints do ComexStat)
- Testes de qualidade de dados (unicidade, nao-nulidade, integridade referencial)
- Documentacao automatica da linhagem dos dados
- Geracao de modelos materializados para consultas rapidas

### 5. PostgreSQL - Banco de Dados de Servico

Substitui o SQLite atual (usado pelo TypeORM para SCM) e as agregacoes em memoria com cache de 24h.

**Responsabilidades:**
- Armazenamento das tabelas Gold pre-computadas
- Servir consultas da API com indices otimizados
- PostGIS para dados geoespaciais (SIGMINE)
- JSONB para dados semi-estruturados (GeoJSON)
- Suporte a leituras concorrentes

### 6. FastAPI - Nova Camada de API

Substitui o NestJS como servidor HTTP.

**Responsabilidades:**
- Servir dados pre-computados do PostgreSQL (leitura pura, sem logica de negocio)
- Documentacao automatica via OpenAPI/Swagger
- Paginacao e filtros sobre tabelas Gold

### 7. Airbyte (Opcional) - Ingestao Padronizada

Pode substituir os clientes HTTP customizados (`COMEXSTAT_HTTP_CLIENT`, `RDE_HTTP_CLIENT`).

**Responsabilidades:**
- Conectores pre-construidos para APIs REST e OData
- Gerenciamento de estado de sincronizacao (incremental)
- Normalizacao automatica de schemas

---

## Camadas do Data Lakehouse

### Bronze - Dados Brutos

Dados exatamente como recebidos das fontes externas, sem nenhuma transformacao.

| Fonte | Formato | Particionamento | Exemplo de caminho no MinIO |
|-------|---------|-----------------|----------------------------|
| ComexStat API | JSON | `ano=YYYY/mes=MM/dia=DD` | `bronze/comexstat/ano=2026/mes=05/dia=09/export_response.json` |
| RDE OData API | JSON | `ano=YYYY/mes=MM/dia=DD` | `bronze/rde/ano=2026/mes=05/dia=09/todos_registros.json` |
| SCM (ANM) | ZIP/CSV | `ano=YYYY/mes=MM/dia=DD` | `bronze/scm/ano=2026/mes=05/dia=09/Processo.txt` |
| SIGMINE | Shapefile | `ano=YYYY/semana=WW` | `bronze/sigmine/ano=2026/semana=19/AREA_SERVIDAO.shp` |

### Silver - Dados Limpos e Tipados

Dados limpos, tipados, deduplicados e filtrados para o Ceara. Armazenados como Parquet no MinIO.

| Tabela | Descricao | Transformacoes aplicadas |
|--------|-----------|--------------------------|
| `silver_comexstat_trade` | Dados de comercio exterior | Tipagem de colunas, normalizacao de nomes de paises/estados, conversao de valores para numerico |
| `silver_rde_registros` | Registros de capital estrangeiro | Filtro `UfPessoaNacional LIKE '%CE%'`, tipagem, deduplicacao por `CodigoRDE` |
| `silver_scm_processos` | Processos minerarios do Ceara | Filtro por municipios com `SGUF = 'CE'`, deduplicacao por `DSProcesso`, joins com tabelas de referencia |
| `silver_sigmine_layers` | Camadas geoespaciais | Conversao shapefile para GeoJSON, filtro por bounding box do Ceara |

### Gold - Tabelas Pre-Agregadas

Tabelas prontas para servir a API, carregadas no PostgreSQL. Cada tabela corresponde a um endpoint ou componente de resposta da API.

| Tabela Gold | Endpoint API | Metodo NestJS original |
|-------------|-------------|------------------------|
| `gold_comexstat_summary` | `GET /comexstat/summary` | `getSummaryData()` |
| `gold_comexstat_summary_history` | `GET /comexstat/summary/history` | `getSummaryHistory()` |
| `gold_comexstat_timeseries` | `GET /comexstat/timeseries` | `getTimeSeries()` |
| `gold_comexstat_partners` | `GET /comexstat/partners` | `getPartnerCountries()` |
| `gold_comexstat_products` | `GET /comexstat/products` | `getTopProducts()` |
| `gold_comexstat_national_comparison` | `GET /comexstat/national-comparison` | `getNationalComparison()` |
| `gold_comexstat_states_ranking` | `GET /comexstat/states-ranking` | `getStatesRanking()` |
| `gold_comexstat_dashboard` | `GET /comexstat/dashboard` | Combinacao de summary + products + partners |
| `gold_rde_todos_registros` | `GET /rde/todos-registros` | `getTodosRegistros()` |
| `gold_rde_registros_ied` | `GET /rde/registros-ied` | `getRegistrosIed()` |
| `gold_scm_processos` | `GET /scm/processos` | Dados do SCM com joins |
| `gold_scm_analytics_*` | `GET /scm/analytics/*` | `getProcessosByFase()`, `getProcessosByTipo()`, etc. |
| `gold_sigmine_layers` | `GET /sigmine/:layer` | `getLayer()` |

---

## Diagrama de Arquitetura

```
                          FONTES EXTERNAS
            +----------------+----------------+----------------+
            |                |                |                |
     ComexStat API      RDE OData       ANM (SCM ZIP)    SIGMINE (SHP)
            |                |                |                |
            v                v                v                v
    +---------------------------------------------------------------+
    |                     APACHE AIRFLOW                             |
    |  dag_comexstat_ingestao  |  dag_rde_ingestao                  |
    |  dag_scm_ingestao        |  dag_sigmine_ingestao              |
    +---------------------------------------------------------------+
            |                |                |                |
            v                v                v                v
    +---------------------------------------------------------------+
    |                    MinIO - BRONZE                              |
    |  JSON (ComexStat)  |  JSON (RDE)  |  CSV (SCM)  |  SHP       |
    |  Dados brutos, particionados por data de ingestao             |
    +---------------------------------------------------------------+
            |
            v
    +---------------------------------------------------------------+
    |              SPARK / PANDAS - Processamento                   |
    |  - Parsing CSV (delimitador ;)                                |
    |  - Filtragem Ceara (SGUF='CE', state_id=23, bbox)            |
    |  - Tipagem e deduplicacao                                     |
    |  - Conversao shapefile -> GeoJSON                             |
    +---------------------------------------------------------------+
            |
            v
    +---------------------------------------------------------------+
    |                    MinIO - SILVER                              |
    |  Parquet tipado e filtrado para Ceara                          |
    +---------------------------------------------------------------+
            |
            v
    +---------------------------------------------------------------+
    |                        dbt                                    |
    |  - Pre-agregacoes (summary, timeseries, ranking)              |
    |  - Calculos (toMillions, tradeBalance, participation)         |
    |  - Window functions (RANK, PERCENT)                           |
    |  - Testes de qualidade                                        |
    +---------------------------------------------------------------+
            |
            v
    +----------------------------+----------------------------------+
    |     MinIO - GOLD           |         PostgreSQL               |
    |  (Parquet arquivamento)    |  (Tabelas de servico)            |
    +----------------------------+----------------------------------+
                                          |
                                          v
                                 +------------------+
                                 |     FastAPI       |
                                 |  API read-only    |
                                 +------------------+
                                          |
                                          v
                                    Clientes/Frontend
```

---

## Justificativa Tecnologica

### PostgreSQL no lugar de SQLite

| Criterio | SQLite (atual) | PostgreSQL (novo) |
|----------|---------------|-------------------|
| Concorrencia | Single-writer, bloqueio em escrita | MVCC, multiplos leitores/escritores |
| Indexacao | Basica (B-tree) | B-tree, GIN, GiST, BRIN, parcial |
| Geodados | Nao suporta nativamente | PostGIS com funcoes espaciais completas |
| JSON | Funcoes basicas | JSONB com indices GIN, operadores ricos |
| Escalabilidade | Limitado a um unico arquivo | Connection pooling, replicas de leitura |
| Monitoramento | Inexistente | pg_stat_statements, pg_stat_activity |

**Impacto direto:** O `ScmRepositoryService` hoje usa TypeORM sobre SQLite. Com PostgreSQL, queries como `getProcessosByFase()` podem usar indices compostos e CTEs para performance superior.

### Airflow no lugar de NestJS @Cron

| Criterio | NestJS @Cron (atual) | Airflow (novo) |
|----------|---------------------|----------------|
| Visibilidade | Apenas logs no stdout | UI web com historico de execucoes |
| Retry | Manual com `for` loop (ex: 3 tentativas em `downloadAndExtractData()`) | Politica declarativa por task (`retries=3, retry_delay=timedelta(minutes=5)`) |
| Dependencias | Imperativo com `await` sequencial | Declarativo com operador `>>` e `TaskGroup` |
| Monitoramento | Sem dashboard | Gantt chart, graficos de duracao, alertas por email/Slack |
| Paralelismo | `Promise.all()` manual | Executor configuravel (Local, Celery, Kubernetes) |
| Backfill | Nao suporta | Nativo, com `catchup=True` |

**Impacto direto:** O `ScmSchedulerService` com `@Cron(EVERY_DAY_AT_2AM)` vira uma DAG com sensor de freshness, retry automatico e visibilidade completa de cada etapa.

### MinIO no lugar de sistema de arquivos

| Criterio | File System (atual) | MinIO (novo) |
|----------|-------------------|--------------|
| Versionamento | Nenhum | Versionamento de objetos nativo |
| Auditoria | Nenhuma | Logs de acesso, politicas de retencao |
| Replay | Impossivel (dados sobrescritos) | Qualquer versao anterior pode ser relida |
| Compartilhamento | Local ao servidor | API S3-compatible, acessivel por qualquer worker |
| Backup | Manual | Replicacao e erasure coding |

**Impacto direto:** Hoje o `ScmCsvService` baixa o ZIP para `data/scm/` e extrai para `data/scm/extracted/`. Se o download falhar no meio, os dados anteriores ja foram sobrescritos. Com MinIO, cada ingestao cria uma nova versao.

### dbt no lugar de agregacoes em JavaScript in-memory

| Criterio | JavaScript in-memory (atual) | dbt (novo) |
|----------|------------------------------|------------|
| Linguagem | JavaScript com `Map`, `forEach`, `sort` | SQL padrao, versionado em Git |
| Linhagem | Nenhuma | Grafo de dependencias automatico |
| Testes | Nenhum nos dados | `unique`, `not_null`, `accepted_values`, `relationships` |
| Documentacao | Apenas JSDoc | Descricoes em YAML, site de documentacao gerado |
| Reusabilidade | Duplicacao de logica entre metodos | Macros e refs entre modelos |
| Performance | Limitado a RAM do servidor | Delegado ao engine SQL (PostgreSQL) |

**Impacto direto:** O metodo `getStatesRanking()` hoje faz 5 chamadas paralelas a API ComexStat e agrega tudo em JavaScript com Maps e arrays. Com dbt, isso vira uma unica query SQL com CTEs e window functions, executada no PostgreSQL.

### FastAPI no lugar de NestJS

| Criterio | NestJS (atual) | FastAPI (novo) |
|----------|---------------|----------------|
| Complexidade | Controllers, Services, Modules, DTOs, Guards | Routes simples com type hints |
| Proposito | Full-stack (logica de negocio + API) | Read-only (serve dados pre-computados) |
| Ecossistema | TypeScript/Node.js | Python (alinhado com Airflow, Spark, Pandas, dbt) |
| Documentacao | Swagger via decoradores | OpenAPI automatico via type hints |
| Performance | Suficiente para leitura | async/await nativo, Uvicorn com workers |

**Impacto direto:** A nova API nao tera logica de negocio. Todos os metodos complexos do `ComexstatService` (ex: `getSummaryData()`, `getTimeSeries()`) serao substituidos por `SELECT * FROM gold_comexstat_summary WHERE ...`. Isso reduz a API a um CRUD de leitura sobre tabelas pre-computadas.

---

## Requisitos de Infraestrutura

| Componente | Recomendacao minima | Observacao |
|-----------|---------------------|------------|
| Airflow | 2 vCPU, 4GB RAM, 20GB disco | Scheduler + Webserver + 1 Worker |
| MinIO | 2 vCPU, 4GB RAM, 100GB disco | Single-node para desenvolvimento |
| Spark | 4 vCPU, 8GB RAM | Apenas se volumes justificarem (senao usar Pandas) |
| PostgreSQL | 2 vCPU, 4GB RAM, 50GB disco | Com extensao PostGIS |
| FastAPI | 1 vCPU, 2GB RAM | Stateless, escalavel horizontalmente |
| dbt | Executa no worker do Airflow | Sem infraestrutura dedicada |

---

## Proximos Passos

1. **`04-pipelines-ingestao.md`** - Design detalhado das 4 DAGs do Airflow
2. **`05-modelos-transformacao.md`** - Mapeamento de cada metodo NestJS para modelo dbt/Spark
