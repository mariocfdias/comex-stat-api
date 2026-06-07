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

- [x] `dag_scm_ingestao.py` implementado com código Python real (sem TODOs)
- [x] `dag_comexstat_ingestao.py` implementado com código Python real (18 chamadas API)
- [x] `dag_rde_ingestao.py` implementado com paginação OData completa
- [x] `dag_sigmine_ingestao.py` implementado com geopandas + PostGIS
- [ ] DAGs carregadas no Airflow sem erros de import

---

## Fase 2 — Pipelines de Ingestão (Semanas 3-6)

### 2.1 Pipeline SCM — PRIORIDADE 1 (Semana 3)

**Razão**: Já opera em batch. Menor risco. Valida toda a infraestrutura.

- [x] Task `check_freshness`: verificar timestamp no MinIO (threshold 48h)
- [x] Task `download_zip`: baixar ZIP da ANM (verify=False, timeout 600s, User-Agent spoofing)
- [x] Task `extract_and_parse`: extrair 7 arquivos TXT com pandas (sep=";", encoding="latin-1")
- [x] Task `filter_ceara`: replicar `ScmCsvService.filterDataForCeara()` (cascata exata)
  - [x] Filtrar municípios SGUF = 'CE'
  - [x] Cascata: município → ProcessoMunicipio → Processo → ProcessoSubstancia
  - [x] Salvar como Parquet no MinIO staging-data
- [x] Task `load_reference_tables`: REPLACE em raw.scm_fase_processo/tipo/municipio/substancia
- [x] Task `load_processos`: TRUNCATE + INSERT em chunks de 500 (replica NestJS chunkSize)
- [x] Task `compute_gold`: materializar gold.scm_by_fase/tipo/municipio/substancia
- [ ] DAG executando com sucesso por 3+ dias consecutivos
- [x] Modelos dbt staging SCM (6 modelos)
- [x] Modelos dbt gold SCM (6 modelos: by_fase, by_tipo, by_municipio, by_substancia, processos, resumo)
- [ ] Testes dbt SCM passando (not_null, unique, relationships)
- [ ] **Validação**: contagens SQLite atual == PostgreSQL novo

### 2.2 Pipeline ComexStat — PRIORIDADE 2 (Semanas 4-5)

**Razão**: Maior ganho — elimina 5 chamadas HTTP paralelas de 60s.

- [x] Task `extract_ce_export/import`: replicar `queryGeneral({ flow })` com monthDetail=True
- [x] Task `extract_ce_partners_*`: `queryGeneral` com details=['country']
- [x] Task `extract_ce_products_heading/ncm_*`: `queryGeneral` com details=['heading'/'ncm']
- [x] Task `extract_national_*`: dados nacionais (total + by state + by state+sector/partner/product)
- [x] Task `transform_silver`: normalizar campos (country vs countryName, etc.) com _normalize_row()
- [x] Task `compute_gold_summary`: 3 períodos × 2 fluxos com ranking CE
- [x] Task `compute_gold_timeseries`: série mensal e anual
- [x] Task `compute_gold_partners`: top N por fluxo/período com percentual
- [x] Task `compute_gold_products`: 3 níveis de agregação (ncm/heading/chapter)
- [x] Task `compute_gold_national`: **substitui 5 chamadas paralelas por 1 Pandas** (+ states ranking)
- [x] Task `compute_gold_dashboard`: combinar tabelas gold existentes
- [x] Task `load_postgresql`: validações de invariante (trade_balance, participation range)
- [ ] Pool `comexstat_api` configurado no Airflow UI (max 3 slots)
- [ ] DAG executando por 5+ dias consecutivos
- [ ] Modelos dbt staging (10 modelos)
- [x] Modelos dbt gold (2 modelos: summary_enriched, dashboard)
- [x] Testes dbt: `trade_balance = exports - imports` (validado em load_postgresql)
- [ ] Índices PostgreSQL criados (4 índices)

### 2.3 Pipeline RDE — PRIORIDADE 3 (Semana 5.5)

- [x] Task `extract_todos_registros`: paginação completa OData (PAGE_SIZE=1000)
- [x] Task `extract_registros_ied`: paginação completa
- [x] Task `store_bronze` + `transform_silver`: deduplicação + Parquet com PascalCase preservado
- [x] Task `load_postgresql`: REPLACE + validações de invariante
- [ ] DAG executando por 3+ dias consecutivos
- [x] Modelos dbt gold (2 modelos: rde_summary, rde_by_sistema)
- [x] Testes dbt: Ano >= 2011, Mes em [1..12], UfPessoaNacional contém 'CE' (no schema.yml)

### 2.4 Pipeline Sigmine — PRIORIDADE 4 (Semana 6)

- [x] Task `download_shapefiles`: copiar de static/ para MinIO (volume montado em docker-compose)
- [x] Task `convert_geojson`: converter com geopandas (reproject EPSG:4326)
- [x] Task `filter_ceara_bbox`: replicar `GeographicFilterService.filterByCearaBounds()`
  - [x] Bounding box: W=-41.5, E=-37.2, S=-7.87, N=-2.78
  - [x] Layer 'CE' sem filtro (replica NestJS)
  - [x] Fallback em caso de erro (replica NestJS try/catch)
- [x] Task `load_postgis`: geopandas.to_postgis() com geometry + properties JSONB
- [ ] DAG executando por 2+ semanas consecutivas
- [x] Índice GIST na coluna geometry (CREATE INDEX USING GIST)

---

## Fase 3 — API FastAPI (Semanas 5-7)

### 3.1 Infraestrutura

- [x] Pool asyncpg embutido no main.py (min_size=2, max_size=10)
- [ ] `config.py`: settings via pydantic-settings (estrutura simplificada em main.py por ora)
- [ ] Estrutura de pastas: `routers/`, `models/`, `services/`, `schemas/` (pendente refatoração)

### 3.2 Modelos Pydantic (DTOs com aliases camelCase)

- [ ] `models/comexstat.py` (40+ modelos com alias) — pendente refatoração
- [ ] `models/rde.py` (PascalCase preservado via alias) — pendente refatoração
- [ ] `models/scm.py` — pendente
- [ ] `models/sigmine.py` (FeatureCollection GeoJSON) — pendente

### 3.3 Routers (implementação real)

#### ComexStat (9 endpoints)

- [x] GET `/comexstat/summary` → `gold.gold_comexstat_summary`
- [x] GET `/comexstat/summary-history` → `gold.gold_comexstat_timeseries`
- [x] GET `/comexstat/timeseries` → `gold.gold_comexstat_timeseries`
- [x] GET `/comexstat/partners` → `gold.gold_comexstat_partners`
- [x] GET `/comexstat/products` → `gold.gold_comexstat_products`
- [ ] GET `/comexstat/national-comparison` → `gold.gold_comexstat_national_comparison`
- [x] GET `/comexstat/national-comparison/states-ranking` → pre-computed + 1 SELECT
- [x] GET `/comexstat/dashboard` → combina summary + partners + products
- [x] DELETE `/comexstat/cache` → no-op implementado

#### RDE (2 endpoints)

- [x] GET `/rde/todos-registros` com paginação (skip, top, orderAno, orderMes)
- [x] GET `/rde/registros-ied` com paginação

#### SCM (17 endpoints)

- [x] 17 endpoints implementados com queries PostgreSQL

#### Sigmine/Layers (6 endpoints)

- [x] 6 endpoints com `ST_AsGeoJSON` via PostGIS

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
| Fase 2: Pipelines | 70 | 47 | 23 |
| Fase 3: FastAPI | 46 | 29 | 17 |
| Fase 4: Validação | 20 | 0 | 20 |
| Fase 5: Cutover | 7 | 0 | 7 |
| **Total** | **179** | **86** | **93** |

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
| 2026-06-07 | FastAPI usa asyncpg direto (sem SQLAlchemy async) | Mais simples para queries raw; SQLAlchemy async adicionado quando refatorar routers |
| 2026-06-07 | DAGs usam pandas para gold (sem dbt no fluxo principal) | dbt como camada opcional de validação; pandas direto é mais simples para inicio |
| 2026-06-07 | Sigmine monta static/ como volume read-only no Airflow | ANM URLs de shapefile não confirmadas; static/ já existe e contém dados válidos |

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
