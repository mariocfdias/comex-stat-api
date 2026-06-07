# Rastreamento de Progresso — Migração NestJS → Plataforma de Dados

**Projeto**: comex-stat-api  
**Início**: 2026-06-07  
**Objetivo**: Migrar API NestJS para FastAPI + PostgreSQL + Airflow + dbt  
**Referência**: `docs/migration-data-platform/07-estrategia-migracao.md`  
**Princípio**: Zero downtime — NestJS permanece operacional durante toda a migração

---

## Legenda

- `[ ]` Pendente
- `[~]` Em andamento
- `[x]` Concluído
- `[!]` Bloqueado

---

## Fase 1 — Infraestrutura (Semanas 1-2)

### 1.1 Arquivos Base

- [x] `.env.example` criado com todas as variáveis necessárias
- [x] `docker-compose.yml` criado com todos os serviços
- [x] `data-platform/scripts/init_postgres.sql` criado
- [x] `data-platform/scripts/init_airflow_db.sh` criado
- [x] `data-platform/scripts/init_minio.sh` criado
- [x] Estrutura de diretórios `data-platform/` criada

### 1.2 PostgreSQL 16 + PostGIS

- [ ] Container PostgreSQL rodando (`docker compose up -d postgres`)
- [ ] Extensão PostGIS habilitada (`SELECT PostGIS_Version();`)
- [ ] Schema `raw` criado e acessível
- [ ] Schema `staging` criado e acessível
- [ ] Schema `gold` criado e acessível
- [ ] Usuário `api_reader` criado (somente leitura em `gold`)
- [ ] Usuário `dbt_user` criado (leitura/escrita em todos os schemas)
- [ ] Conexão validada: `psql -h localhost -U postgres -d comexstat_platform`

### 1.3 MinIO (Object Storage S3-compatible)

- [ ] Container MinIO rodando (`docker compose up -d minio`)
- [ ] Bucket `raw-data` criado
- [ ] Bucket `staging-data` criado
- [ ] Bucket `backups` criado
- [ ] Console MinIO acessível: http://localhost:9001

### 1.4 Apache Airflow 2.9

- [ ] `docker compose up -d airflow-init` executado com sucesso
- [ ] `docker compose up -d airflow-webserver airflow-scheduler` rodando
- [ ] UI Airflow acessível: http://localhost:8080 (admin/admin)
- [ ] Conexão `comexstat_api` configurada na UI
- [ ] Conexão `rde_api` configurada na UI
- [ ] Conexão `anm_api` configurada na UI
- [ ] Conexão `postgres_default` configurada na UI
- [ ] Conexão `minio_default` configurada na UI
- [ ] Pool `comexstat_api` criado (max 3 slots)
- [ ] 4 DAGs visíveis na UI sem erros de import

### 1.5 dbt (Data Build Tool)

- [x] `data-platform/dbt/dbt_project.yml` criado
- [x] `data-platform/dbt/profiles.yml.example` criado
- [ ] `~/.dbt/profiles.yml` configurado (a partir do exemplo)
- [ ] `dbt debug --project-dir data-platform/dbt` passando
- [ ] `dbt compile` sem erros

### 1.6 FastAPI (Placeholder — Fase 1)

- [x] `data-platform/fastapi/main.py` criado (34 endpoints placeholder)
- [x] `data-platform/fastapi/Dockerfile` criado
- [x] `data-platform/fastapi/requirements.txt` criado
- [ ] Container `fastapi` buildando sem erros
- [ ] GET http://localhost:8000/health retornando `{"status": "ok"}`
- [ ] Swagger UI acessível: http://localhost:8000/docs
- [ ] 34 endpoints listados no Swagger

### 1.7 Airflow DAGs (Esqueletos)

- [x] `dag_scm_ingestao.py` criado (esqueleto com TODOs)
- [x] `dag_comexstat_ingestao.py` criado (esqueleto com TODOs)
- [x] `dag_rde_ingestao.py` criado (esqueleto com TODOs)
- [x] `dag_sigmine_ingestao.py` criado (esqueleto com TODOs)
- [ ] DAGs carregadas no Airflow sem erros de import

---

## Fase 2 — Pipelines de Ingestão (Semanas 3-6)

### 2.1 Pipeline SCM — PRIORIDADE 1 (Semana 3)

**Razão**: Já opera em batch. Menor risco. Valida toda a infraestrutura.

- [ ] Task `check_freshness`: verificar timestamp no MinIO
- [ ] Task `download_zip`: baixar ZIP da ANM (verify=False, timeout 600s)
- [ ] Task `extract_csvs`: extrair 7 arquivos TXT para MinIO bronze
- [ ] Task `parse_and_filter`: replicar `ScmCsvService.filterDataForCeara()`
  - [ ] Filtrar municípios SGUF = 'CE'
  - [ ] Cascata: município → processo-município → processo
  - [ ] Salvar como Parquet no MinIO silver
- [ ] Task `load_reference_tables`: fases, tipos, municípios, substâncias
- [ ] Task `load_main_tables`: processos em chunks de 500 (replica NestJS)
- [ ] Task `compute_analytics`: materializar tabelas gold
- [ ] DAG executando com sucesso por 3+ dias consecutivos
- [ ] Modelos dbt staging SCM (6 modelos)
- [ ] Modelos dbt gold SCM (12 modelos: processos, fases, tipos, municípios, substâncias, relações, analytics)
- [ ] Testes dbt SCM passando (not_null, unique, relationships)
- [ ] **Validação**: contagens SQLite atual == PostgreSQL novo

### 2.2 Pipeline ComexStat — PRIORIDADE 2 (Semanas 4-5)

**Razão**: Maior ganho — elimina 5 chamadas HTTP paralelas de 60s.

- [ ] Task `extract_export_data`: replicar `queryGeneral({ flow: 'export' })`
- [ ] Task `extract_import_data`: replicar `queryGeneral({ flow: 'import' })`
- [ ] Task `store_bronze`: salvar JSONs no MinIO particionado por data
- [ ] Task `transform_silver`: normalizar campos (country vs countryName, etc.)
- [ ] Task `compute_gold_summary`: todos os tipos de período
- [ ] Task `compute_gold_timeseries`: mensal e anual
- [ ] Task `compute_gold_partners`: top N por fluxo/período
- [ ] Task `compute_gold_products`: 3 níveis de agregação (ncm/heading/chapter)
- [ ] Task `compute_gold_national`: **substitui 5 chamadas paralelas por 1 Pandas**
- [ ] Task `compute_gold_dashboard`: combinar tabelas
- [ ] Task `load_postgresql`: carregar tabelas gold
- [ ] Pool `comexstat_api` limitando a 3 conexões simultâneas
- [ ] DAG executando por 5+ dias consecutivos
- [ ] Modelos dbt staging (10 modelos)
- [ ] Modelos dbt gold (12 modelos)
- [ ] Testes dbt: `trade_balance = exports - imports`, participação em [0,100]
- [ ] Índices PostgreSQL criados (4 índices)

### 2.3 Pipeline RDE — PRIORIDADE 3 (Semana 5.5)

- [ ] Task `extract_todos_registros`: paginação completa (PAGE_SIZE=1000)
- [ ] Task `extract_ied_records`: paginação completa
- [ ] Task `store_bronze` + `transform_silver`: Parquet com PascalCase preservado
- [ ] Task `load_postgresql`: TRUNCATE + INSERT
- [ ] DAG executando por 3+ dias consecutivos
- [ ] Modelos dbt gold (2 modelos)
- [ ] Testes dbt: Ano >= 2011, Mes em [1..12], UfPessoaNacional contém 'CE'

### 2.4 Pipeline Sigmine — PRIORIDADE 4 (Semana 6)

- [ ] Task `download_shapefiles`: copiar de static/ para MinIO
- [ ] Task `convert_geojson`: converter com geopandas/fiona
- [ ] Task `filter_ceara`: replicar `GeographicFilterService.filterByCearaBounds()`
  - [ ] Bounding box: W=-41.5, E=-37.2, S=-7.9, N=-2.8
  - [ ] Layer 'ce' sem filtro
  - [ ] Fallback em caso de erro
- [ ] Task `load_postgis`: carregar geometria + JSONB
- [ ] DAG executando por 2+ semanas consecutivas
- [ ] Índice GIST na coluna geometry

---

## Fase 3 — API FastAPI (Semanas 5-7)

### 3.1 Infraestrutura

- [ ] `config.py`: settings via pydantic-settings
- [ ] `database.py`: engine async SQLAlchemy com pool_size=20
- [ ] Estrutura de pastas: `routers/`, `models/`, `services/`, `schemas/`

### 3.2 Modelos Pydantic (DTOs com aliases camelCase)

- [ ] `models/comexstat.py` (40+ modelos com alias)
- [ ] `models/rde.py` (PascalCase preservado via alias)
- [ ] `models/scm.py`
- [ ] `models/sigmine.py` (FeatureCollection GeoJSON)

### 3.3 Routers (implementação real)

#### ComexStat (9 endpoints)

- [ ] GET `/comexstat/summary` → `gold.gold_comexstat_summary`
- [ ] GET `/comexstat/summary-history` → `gold.gold_comexstat_summary_history`
- [ ] GET `/comexstat/timeseries` → `gold.gold_comexstat_timeseries`
- [ ] GET `/comexstat/partners` → `gold.gold_comexstat_partners`
- [ ] GET `/comexstat/products` → `gold.gold_comexstat_products`
- [ ] GET `/comexstat/national-comparison` → `gold.gold_comexstat_national_comparison`
- [ ] GET `/comexstat/national-comparison/states-ranking` → query com 3 JOINs
- [ ] GET `/comexstat/dashboard` → múltiplas queries
- [ ] DELETE `/comexstat/cache` → no-op

#### RDE (2 endpoints)

- [ ] GET `/rde/todos-registros` com paginação (skip, top, orderAno, orderMes)
- [ ] GET `/rde/registros-ied` com paginação

#### SCM (17 endpoints)

- [ ] 17 endpoints implementados com queries PostgreSQL

#### Sigmine/Layers (6 endpoints)

- [ ] 6 endpoints com `ST_AsGeoJSON` via PostGIS

### 3.4 Testes de Contrato (Golden Files)

- [ ] Script `record_golden_responses.py`: gravar respostas do NestJS
- [ ] Suite pytest com deepdiff: comparar campo a campo
- [ ] 100% dos endpoints com respostas idênticas
- [ ] CI/CD integrado

---

## Fase 4 — Validação Paralela (Semanas 7-9)

- [ ] nginx com `mirror` (shadow traffic NestJS → FastAPI)
- [ ] Script `compare_shadow_responses.py` (deepdiff, a cada 15min)
- [ ] Zero divergências por 48h consecutivas
- [ ] Benchmark: p99 < 200ms todos os endpoints
- [ ] `/comexstat/national-comparison/states-ranking`: 100-600x mais rápido
- [ ] Teste de carga k6 (50 VUs, 5min, p99 < 200ms, erro < 1%)
- [ ] Todos os casos de borda validados

### Critérios de Go/No-Go (todos obrigatórios)

- [ ] 100% dos endpoints retornando respostas idênticas por 7 dias
- [ ] Zero divergências no tráfego sombra por 48h
- [ ] p99 < 200ms para todos os endpoints
- [ ] Pipelines Airflow executando por 7+ dias consecutivos
- [ ] Testes dbt 100% passando
- [ ] Zero erros 5xx na FastAPI por 48h
- [ ] Backup PostgreSQL configurado e verificado
- [ ] Procedimento de rollback testado (<5 minutos)

---

## Fase 5 — Cutover (Semana 10)

- [ ] Cutover executado (proxy → FastAPI porta 8000)
- [ ] Métricas T+5min verificadas
- [ ] NestJS em hot standby (2 semanas)
- [ ] 2 semanas de estabilidade confirmadas
- [ ] NestJS descomissionado
- [ ] Documentação atualizada

---

## Resumo

| Fase | Total | Concluídas | Pendentes |
|------|-------|-----------|-----------|
| Fase 1: Infraestrutura | 36 | 10 | 26 |
| Fase 2: Pipelines | 70 | 0 | 70 |
| Fase 3: FastAPI | 46 | 0 | 46 |
| Fase 4: Validação | 20 | 0 | 20 |
| Fase 5: Cutover | 7 | 0 | 7 |
| **Total** | **179** | **10** | **169** |

---

## Log de Decisões

| Data | Decisão | Justificativa |
|------|---------|---------------|
| 2026-06-07 | `postgis/postgis:16-3.4` como imagem base | PostgreSQL 16 + PostGIS 3.4 em imagem oficial |
| 2026-06-07 | `apache/airflow:2.9-python3.11` | Versão estável com Python 3.11 |
| 2026-06-07 | Banco `airflow` separado do `comexstat_platform` | Isolamento — falha do Airflow não afeta dados |
| 2026-06-07 | `LocalExecutor` para Airflow | Suficiente para 4 DAGs; evita complexidade do Celery |
| 2026-06-07 | FastAPI placeholder ativo desde Fase 1 | Valida roteamento e CORS antes da implementação real |
| 2026-06-07 | NestJS não modificado durante toda a migração | Zero downtime — hot standby até Fase 5 |
| 2026-06-07 | Prioridade SCM > ComexStat > RDE > Sigmine | SCM já é batch; ComexStat tem maior ganho de performance |

---

## Referências

| Recurso | URL |
|---------|-----|
| Documentação de arquitetura | `docs/migration-data-platform/` |
| Índice da migração | `docs/migration-data-platform/00-indice.md` |
| Estratégia de migração | `docs/migration-data-platform/07-estrategia-migracao.md` |
| Airflow UI | http://localhost:8080 |
| MinIO Console | http://localhost:9001 |
| FastAPI Docs | http://localhost:8000/docs |
| NestJS API (atual) | http://localhost:3000 |
