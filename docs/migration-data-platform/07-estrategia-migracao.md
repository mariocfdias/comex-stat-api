# 07 - Estrategia de Migracao

Estrategia completa para migrar a API NestJS para a plataforma de dados com FastAPI, garantindo zero downtime e preservacao de todos os contratos de API.

---

## Visao Geral

**Objetivo**: Migrar a API comex-stat-api de NestJS (que consulta APIs externas em tempo real) para FastAPI (que consulta tabelas pre-computadas no PostgreSQL), sem interromper o servico e mantendo 100% de compatibilidade com os clientes existentes.

**Abordagem**: Construir a nova plataforma em paralelo, executar trafego sombra para validar, e entao fazer o cutover.

### Principios

1. **Zero downtime**: Os clientes nunca percebem a migracao
2. **Preservacao de contrato**: Todos os 34+ endpoints retornam respostas identicas
3. **Rollback seguro**: A API NestJS permanece como hot standby
4. **Validacao exaustiva**: Comparacao automatizada de respostas antes do cutover

### Arquitetura de Migracao

```
                    ┌─────────────────────────────────────┐
                    │         Reverse Proxy / LB           │
                    │    (nginx / ALB / Cloudflare)        │
                    └──────────┬──────────┬───────────────┘
                               │          │
                  ┌────────────▼──┐  ┌────▼────────────┐
                  │  NestJS API   │  │  FastAPI (nova)  │
                  │  (porta 3000) │  │  (porta 8000)   │
                  └──────┬────────┘  └──────┬──────────┘
                         │                  │
              ┌──────────▼──────────┐  ┌────▼──────────────┐
              │   APIs Externas     │  │   PostgreSQL       │
              │  - ComexStat API    │  │  (tabelas gold)    │
              │  - RDE OData        │  │  - PostGIS         │
              │  - ANM/Sigmine      │  │  - Dados dbt       │
              └─────────────────────┘  └────────────────────┘
```

---

## Fase 1: Setup de Infraestrutura (Semanas 1-2)

### 1.1 Deploy do PostgreSQL

- Instalar PostgreSQL 16+ com extensao PostGIS
- Configurar schemas: `raw`, `staging`, `gold`
- Criar usuario dedicado para a API (somente leitura no schema `gold`)
- Criar usuario dedicado para o dbt (leitura/escrita em todos os schemas)
- Configurar backup automatizado

```sql
-- Setup inicial do banco
CREATE DATABASE comexstat_platform;
\c comexstat_platform

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA raw;      -- dados brutos ingeridos
CREATE SCHEMA staging;  -- dados limpos e normalizados
CREATE SCHEMA gold;     -- dados prontos para consumo da API

-- Usuario da API (somente leitura)
CREATE USER api_reader WITH PASSWORD '...';
GRANT USAGE ON SCHEMA gold TO api_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO api_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO api_reader;

-- Usuario do dbt (escrita)
CREATE USER dbt_user WITH PASSWORD '...';
GRANT ALL ON SCHEMA raw, staging, gold TO dbt_user;
```

### 1.2 Deploy do Apache Airflow

- Opcao A: Docker Compose (desenvolvimento/staging)
- Opcao B: Managed Airflow (producao - MWAA, Cloud Composer, Astronomer)
- Configurar conexoes: PostgreSQL, MinIO/S3, APIs externas
- Configurar pools para controle de concorrencia nas APIs externas
- Configurar alertas (email, Slack)

```yaml
# docker-compose.airflow.yml (simplificado)
services:
  airflow-webserver:
    image: apache/airflow:2.9-python3.11
    environment:
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://...
      AIRFLOW__CORE__EXECUTOR: LocalExecutor
    volumes:
      - ./dags:/opt/airflow/dags
      - ./plugins:/opt/airflow/plugins
    ports:
      - "8080:8080"

  airflow-scheduler:
    image: apache/airflow:2.9-python3.11
    volumes:
      - ./dags:/opt/airflow/dags
```

### 1.3 Deploy do MinIO / Armazenamento de Objetos

- Deploy MinIO para ambiente local/staging
- Ou configurar bucket S3 para producao
- Criar buckets: `raw-data`, `staging-data`, `backups`

### 1.4 Configurar Projeto dbt

```
dbt_comexstat/
├── dbt_project.yml
├── profiles.yml
├── models/
│   ├── staging/
│   │   ├── stg_comexstat_exports.sql
│   │   ├── stg_comexstat_imports.sql
│   │   ├── stg_rde_registros.sql
│   │   ├── stg_scm_processos.sql
│   │   └── stg_sigmine_layers.sql
│   └── gold/
│       ├── gold_comexstat_summary.sql
│       ├── gold_comexstat_summary_history.sql
│       ├── gold_comexstat_timeseries.sql
│       ├── gold_comexstat_partners.sql
│       ├── gold_comexstat_products.sql
│       ├── gold_comexstat_national_comparison.sql
│       ├── gold_comexstat_states_ranking.sql
│       ├── gold_rde_todos_registros.sql
│       ├── gold_rde_registros_ied.sql
│       └── gold_sigmine_layers.sql
├── tests/
│   ├── assert_summary_not_null.sql
│   ├── assert_ranking_ordered.sql
│   └── assert_rde_uf_ceara.sql
└── seeds/
    └── country_codes.csv
```

### 1.5 Configurar CI/CD

- Pipeline de deploy para dbt (dbt run + dbt test)
- Pipeline de deploy para FastAPI (Docker build + deploy)
- Pipeline de testes de contrato (comparacao NestJS vs FastAPI)

### 1.6 Checklist de Infraestrutura

- [ ] PostgreSQL rodando com PostGIS habilitado
- [ ] Schemas `raw`, `staging`, `gold` criados
- [ ] Airflow rodando com scheduler ativo
- [ ] Conexoes Airflow configuradas (PostgreSQL, S3/MinIO)
- [ ] Projeto dbt inicializado e conectado ao PostgreSQL
- [ ] CI/CD basico configurado
- [ ] Monitoramento basico (health checks, logs centralizados)

---

## Fase 2: Construcao dos Pipelines (Semanas 3-6)

### Ordem de Prioridade

| Prioridade | Modulo | Justificativa | Duracao Estimada |
|-----------|--------|---------------|-----------------|
| 1 | **SCM** | Ja possui padrao batch (CSV + SQLite). Menor risco. Valida a abordagem. | 1 semana |
| 2 | **ComexStat** | Mais complexo, maior valor da migracao. 9 endpoints, agregacoes complexas. | 2 semanas |
| 3 | **RDE** | 2 endpoints, dados OData, paginacao simples. | 0.5 semana |
| 4 | **Sigmine** | 6 endpoints GeoJSON, requer PostGIS. | 0.5 semana |

### 2.1 Pipeline SCM (Semana 3)

**Por que primeiro**: O modulo SCM ja opera em modo batch. Ele baixa arquivos CSV da ANM, parseia e armazena em SQLite. Migrar para PostgreSQL valida toda a infraestrutura (Airflow + dbt + PostgreSQL) com risco minimo.

**Passos de desenvolvimento**:

1. **DAG Airflow** `dag_scm_ingest`:
   - Task 1: Baixar CSVs da ANM (processos, fases, tipos, municipios, substancias, processo-municipios, processo-substancias)
   - Task 2: Upload dos CSVs para MinIO/S3 (camada raw)
   - Task 3: Carregar CSVs no PostgreSQL schema `raw`
   - Schedule: Diario as 06:00 UTC

2. **Modelos dbt** (staging):
   - `stg_scm_processos.sql`: Limpeza e tipagem dos processos
   - `stg_scm_fases.sql`: Normalizacao das fases
   - `stg_scm_municipios.sql`: Normalizacao dos municipios
   - (demais tabelas auxiliares)

3. **Modelos dbt** (gold): As tabelas gold sao identicas as tabelas atuais do SQLite, porem no PostgreSQL.

4. **Testes dbt**:
   ```yaml
   # schema.yml
   models:
     - name: gold_scm_processos
       columns:
         - name: DSProcesso
           tests:
             - not_null
             - unique
         - name: IDFaseProcesso
           tests:
             - relationships:
                 to: ref('gold_scm_fases_processo')
                 field: IDFaseProcesso
   ```

**Teste de validacao**: Comparar contagens e amostras entre SQLite atual e PostgreSQL.

### 2.2 Pipeline ComexStat (Semanas 4-5)

**Por que segundo**: E o modulo mais complexo (9 endpoints, agregacoes em memoria) e o que mais se beneficia da migracao (eliminacao de 60s timeouts). Exige maior cuidado.

**Passos de desenvolvimento**:

1. **DAG Airflow** `dag_comexstat_ingest`:
   - Task 1: Chamar API ComexStat `/general` com parametros para exportacoes do Ceara (metricFOB, metricKG, metricCIF)
   - Task 2: Chamar API ComexStat para importacoes
   - Task 3: Chamar API ComexStat para dados nacionais (todos os estados)
   - Task 4: Chamar API ComexStat para dados por pais parceiro
   - Task 5: Chamar API ComexStat para dados por produto (NCM, heading, chapter)
   - Task 6: Chamar API ComexStat para dados por setor ISIC
   - Task 7: Salvar tudo no MinIO/S3 como JSON (camada raw)
   - Task 8: Carregar no PostgreSQL schema `raw`
   - Schedule: Diario as 08:00 UTC
   - Pool: `comexstat_api` (max 3 concorrentes para nao sobrecarregar a API)

2. **Modelos dbt** (staging):
   - `stg_comexstat_exports_mensal.sql`: Exportacoes mensais do Ceara
   - `stg_comexstat_imports_mensal.sql`: Importacoes mensais do Ceara
   - `stg_comexstat_exports_por_pais.sql`: Exportacoes por pais
   - `stg_comexstat_imports_por_pais.sql`: Importacoes por pais
   - `stg_comexstat_exports_por_produto.sql`: Exportacoes por produto
   - `stg_comexstat_imports_por_produto.sql`: Importacoes por produto
   - `stg_comexstat_por_estado.sql`: Dados de todos os estados
   - `stg_comexstat_por_estado_setor.sql`: Dados por estado e setor ISIC
   - `stg_comexstat_por_estado_pais.sql`: Dados por estado e pais
   - `stg_comexstat_por_estado_produto.sql`: Dados por estado e produto

3. **Modelos dbt** (gold) - pre-computando os dados como a API NestJS faz em memoria:
   - `gold_comexstat_summary.sql`: Calcula exports, imports, tradeBalance, tradeCurrent para cada combinacao de period_type
   - `gold_comexstat_summary_history.sql`: Dados mensais agregados
   - `gold_comexstat_timeseries.sql`: Series temporais com pivot export/import/balance/current
   - `gold_comexstat_timeseries_sectors.sql`: Detalhamento por setor ISIC
   - `gold_comexstat_partners.sql`: Top paises parceiros com percentuais
   - `gold_comexstat_products.sql`: Top produtos com percentuais por nivel de agregacao
   - `gold_comexstat_national_comparison.sql`: Participacao e ranking do Ceara
   - `gold_comexstat_states_ranking.sql`: Ranking de estados com top setores/parceiros/produtos

4. **Testes dbt**:
   ```yaml
   models:
     - name: gold_comexstat_summary
       tests:
         - dbt_utils.expression_is_true:
             expression: "trade_balance = exports - imports"
         - dbt_utils.expression_is_true:
             expression: "trade_current = exports + imports"
       columns:
         - name: exports
           tests:
             - not_null
             - dbt_utils.expression_is_true:
                 expression: "exports >= 0"
     - name: gold_comexstat_states_ranking
       tests:
         - dbt_utils.expression_is_true:
             expression: "participation >= 0 AND participation <= 100"
       columns:
         - name: rank
           tests:
             - not_null
             - dbt_utils.accepted_values:
                 values: "generate_series(1, 27)"
   ```

### 2.3 Pipeline RDE (Semana 5.5)

1. **DAG Airflow** `dag_rde_ingest`:
   - Task 1: Chamar API OData `/TodosRegistros` com filtro `contains(UfPessoaNacional,'CE')` (com paginacao)
   - Task 2: Chamar API OData `/RegistrosIED` com mesmo filtro
   - Task 3: Salvar no MinIO/S3
   - Task 4: Carregar no PostgreSQL
   - Schedule: Diario as 07:00 UTC

2. **Modelos dbt**: Mapeamento direto, preservando nomes de campos em PascalCase conforme DTO atual.

3. **Testes dbt**: Verificar que todos os registros tem `UfPessoaNacional` contendo 'CE'.

### 2.4 Pipeline Sigmine (Semana 6)

1. **DAG Airflow** `dag_sigmine_ingest`:
   - Task 1: Baixar shapefiles da ANM (6 layers: AREA_SERVIDAO, ARRENDAMENTO, BLOQUEIO, CE, PROTECAO_FONTE, RESERVAS_GARIMPEIRAS)
   - Task 2: Converter shapefiles para GeoJSON usando ogr2ogr/fiona
   - Task 3: Carregar no PostGIS usando COPY ou ogr2ogr
   - Schedule: Semanal (dados mudam com menor frequencia)

2. **Modelos dbt** (gold):
   - `gold_sigmine_layers.sql`: View materializada que gera FeatureCollection GeoJSON usando `ST_AsGeoJSON`

---

## Fase 3: Construcao da API FastAPI (Semanas 5-7)

> **Nota**: Esta fase sobrepoe a Fase 2. O desenvolvimento da API comeca assim que os primeiros pipelines (SCM) estejam funcionando.

### 3.1 Implementar Routers FastAPI

Implementar todos os endpoints mapeados no documento `06-camada-api-fastapi.md`:

- **Semana 5**: Routers SCM (17 endpoints) - validar contra dados PostgreSQL
- **Semana 5-6**: Routers ComexStat (9 endpoints) - o mais complexo
- **Semana 6**: Routers RDE (2 endpoints)
- **Semana 6-7**: Routers Sigmine (6 endpoints)

### 3.2 Modelos Pydantic

Implementar todos os modelos Pydantic conforme documentado na Secao 3 do documento `06-camada-api-fastapi.md`. Pontos criticos:

- Usar `alias` em todos os campos para manter camelCase na resposta JSON (ex: `trade_balance` -> `tradeBalance`)
- Configurar `model_config = {"populate_by_name": True, "by_alias": True}` em todos os modelos que usam alias
- Campos opcionais devem usar `Optional[type] = None`

### 3.3 Conexao com Banco de Dados

```python
# database.py
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from .config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session
```

### 3.4 Otimizacao de Queries

- Criar indices no PostgreSQL para os filtros mais usados:
  ```sql
  -- ComexStat
  CREATE INDEX idx_summary_period ON gold.gold_comexstat_summary(period_type, period_from, period_to);
  CREATE INDEX idx_partners_flow_period ON gold.gold_comexstat_partners(flow, period_type);
  CREATE INDEX idx_products_flow_agg ON gold.gold_comexstat_products(flow, aggregation, period_from, period_to);
  CREATE INDEX idx_states_ranking ON gold.gold_comexstat_states_ranking(flow, period_from, period_to, rank);

  -- RDE
  CREATE INDEX idx_rde_todos_ano_mes ON gold.gold_rde_todos_registros(ano DESC, mes DESC);
  CREATE INDEX idx_rde_ied_ano_mes ON gold.gold_rde_registros_ied(ano DESC, mes DESC);

  -- Sigmine
  CREATE INDEX idx_sigmine_layer ON gold.gold_sigmine_layers(layer_name);
  CREATE INDEX idx_sigmine_geom ON gold.gold_sigmine_layers USING GIST(geometry);
  ```

### 3.5 Documentacao OpenAPI

- A documentacao Swagger gerada pelo FastAPI deve ser identica a atual (gerada pelo NestJS/Swagger)
- Verificar que todos os endpoints aparecem em `/docs` e `/redoc`
- Manter as mesmas tags: `comexstat`, `rde`, `SCM - Sistema de Cadastro Mineiro`, `layers`
- Manter as mesmas descricoes de operacao

### 3.6 Testes de Contrato

Executar a suite de testes de contrato conforme descrito na Secao 6 do documento `06-camada-api-fastapi.md`:

1. Gravar respostas golden da API NestJS
2. Executar mesmas requisicoes contra FastAPI
3. Comparar campo a campo com DeepDiff

---

## Fase 4: Execucao Paralela e Validacao (Semanas 7-9)

### 4.1 Setup do Reverse Proxy

Configurar nginx (ou ALB) para rotear trafego:

```nginx
upstream nestjs {
    server localhost:3000;
}

upstream fastapi {
    server localhost:8000;
}

server {
    listen 80;

    # Fase de shadow: todo trafego vai para NestJS,
    # mas tambem e espelhado para FastAPI
    location / {
        proxy_pass http://nestjs;
        mirror /mirror;
        mirror_request_body on;
    }

    location = /mirror {
        internal;
        proxy_pass http://fastapi$request_uri;
        proxy_set_header X-Shadow "true";
    }
}
```

### 4.2 Trafego Sombra

- **Todas** as requisicoes sao enviadas para ambas as APIs
- As respostas do NestJS sao retornadas ao cliente
- As respostas do FastAPI sao logadas para comparacao
- Nenhum impacto para o usuario final

### 4.3 Comparacao Automatizada

```python
# scripts/compare_responses.py
"""
Script que consome logs do trafego sombra e compara respostas.
Executa como job periodico (a cada 1h).
"""
import json
from deepdiff import DeepDiff
from collections import Counter

TOLERANCE = 1e-6  # Tolerancia para diferencas de ponto flutuante

def compare_pair(nestjs_response: dict, fastapi_response: dict, endpoint: str):
    diff = DeepDiff(
        nestjs_response,
        fastapi_response,
        significant_digits=6,
        ignore_order=False,
        exclude_paths=["root['timestamp']"],  # Ignorar campos de timestamp
    )

    if diff:
        return {
            "endpoint": endpoint,
            "status": "DIVERGENT",
            "differences": diff.to_dict(),
        }
    return {
        "endpoint": endpoint,
        "status": "MATCH",
    }
```

### 4.4 Benchmarking de Performance

Medir tempos de resposta para todos os endpoints:

```python
# scripts/benchmark.py
import httpx
import time
import statistics

ENDPOINTS = [
    ("/comexstat/summary", {}),
    ("/comexstat/summary-history", {"from": "2023-01", "to": "2023-12"}),
    ("/comexstat/timeseries", {"startYear": 2020, "endYear": 2024}),
    ("/comexstat/partners", {"flow": "export", "topN": 10}),
    ("/comexstat/products", {"flow": "export", "topN": 20}),
    ("/comexstat/national-comparison", {
        "flow": "export", "from": "2023-01", "to": "2023-12"
    }),
    ("/comexstat/national-comparison/states-ranking", {
        "flow": "export", "from": "2023-01", "to": "2023-12"
    }),
    ("/comexstat/dashboard", {}),
    ("/rde/todos-registros", {"top": 100}),
    ("/rde/registros-ied", {"top": 100}),
    ("/layers/ce", {}),
    ("/scm/processos", {"limit": 100}),
]

def benchmark(base_url: str, runs: int = 10):
    client = httpx.Client(base_url=base_url, timeout=120)
    results = {}

    for path, params in ENDPOINTS:
        times = []
        for _ in range(runs):
            start = time.perf_counter()
            resp = client.get(path, params=params)
            elapsed = (time.perf_counter() - start) * 1000  # ms
            times.append(elapsed)
            assert resp.status_code == 200

        results[path] = {
            "min": round(min(times), 1),
            "max": round(max(times), 1),
            "mean": round(statistics.mean(times), 1),
            "p50": round(statistics.median(times), 1),
            "p99": round(sorted(times)[int(len(times) * 0.99)], 1),
        }

    return results


nestjs = benchmark("http://localhost:3000")
fastapi = benchmark("http://localhost:8000")

print(f"{'Endpoint':<55} {'NestJS p50':>12} {'FastAPI p50':>12} {'Ganho':>8}")
print("-" * 95)
for path in nestjs:
    n = nestjs[path]["p50"]
    f = fastapi[path]["p50"]
    gain = f"{n/f:.0f}x" if f > 0 else "N/A"
    print(f"{path:<55} {n:>10.1f}ms {f:>10.1f}ms {gain:>8}")
```

### 4.5 Casos de Borda a Validar

| Caso | Descricao | Validacao |
|------|-----------|-----------|
| Periodos customizados | `periodFrom=2010-02&periodTo=2010-08` | Verificar que dados historicos antigos sao pre-computados |
| Ranges grandes | `startYear=2000&endYear=2024` (25 anos de dados) | Verificar performance e completude |
| Paginacao RDE | `skip=0&top=1000` | Verificar offset e limites |
| GeoJSON grande | Layer `CE` com milhares de features | Verificar tamanho e performance |
| Enums invalidos | `flow=invalid`, `period=xyz` | Verificar mensagens de erro identicas |
| Campos vazios | Requests sem parametros obrigatorios | Verificar HTTP 400 com mesma estrutura |
| Periodos sem dados | `from=2050-01&to=2050-12` | Verificar resposta vazia vs erro |
| Top N extremo | `topN=1` e `topN=1000` | Verificar limites |

### 4.6 Criterios de Aceitacao para Cutover

- [ ] 100% dos endpoints retornam respostas identicas (por 7 dias consecutivos)
- [ ] Zero divergencias no trafego sombra por 48h
- [ ] p99 de latencia < 200ms para todos os endpoints
- [ ] Pipelines Airflow executando com sucesso por 7+ dias
- [ ] Testes dbt passando 100%
- [ ] Nenhum erro 5xx no FastAPI por 48h

---

## Fase 5: Cutover (Semana 10)

### 5.1 Procedimento de Cutover

1. **T-24h**: Verificacao final de todos os criterios de aceitacao
2. **T-2h**: Comunicacao para stakeholders (janela de mudanca)
3. **T-0**: Alterar proxy/DNS para direcionar trafego para FastAPI
   ```nginx
   location / {
       proxy_pass http://fastapi;  # Antes: http://nestjs
   }
   ```
4. **T+5min**: Verificar metricas (error rate, latencia, throughput)
5. **T+1h**: Primeira verificacao de estabilidade
6. **T+24h**: Segunda verificacao de estabilidade

### 5.2 Hot Standby

- NestJS permanece rodando como hot standby por **2 semanas** apos o cutover
- Monitoramento continuo de error rates e latencia
- Capacidade de rollback em menos de 5 minutos (alterar proxy de volta)

### 5.3 Monitoramento Pos-Cutover

| Metrica | SLA | Alerta |
|---------|-----|--------|
| Error rate (5xx) | < 0.1% | Alerta se > 0.5% por 5min |
| Latencia p99 | < 200ms | Alerta se > 500ms por 5min |
| Frescor dos dados | Atualizado diariamente | Alerta se pipeline nao executou em 24h |
| Divergencia de dados | 0 | Alerta em qualquer divergencia |

### 5.4 Procedimento de Rollback

Se problemas forem detectados apos o cutover:

1. Alterar proxy de volta para NestJS (`proxy_pass http://nestjs`)
2. Investigar causa raiz
3. Corrigir e re-validar
4. Agendar novo cutover

### 5.5 Descomissionamento

Apos 2 semanas de estabilidade sem rollback:

1. Remover NestJS do proxy
2. Parar containers NestJS
3. Arquivar repositorio (nao deletar)
4. Atualizar documentacao
5. Remover conexoes com APIs externas (ComexStat, RDE OData)

---

## Analise de Riscos

| Risco | Impacto | Probabilidade | Mitigacao |
|-------|---------|---------------|-----------|
| API ComexStat muda formato de resposta | **Alto** | Baixa | Validacao de schema nos pipelines Airflow. Alertas automaticos em caso de mudanca. Testes dbt com `accepted_values` e `expression_is_true`. |
| Gap de frescor de dados durante migracao | **Medio** | Media | Executar ambos os sistemas simultaneamente. NestJS continua consultando APIs em tempo real enquanto pipelines estabilizam. |
| Periodos customizados nao pre-computados | **Alto** | Media | Pre-computar todos os periodos historicos com granularidade mensal. Para queries adhoc, implementar fallback dinamico que calcula a partir dos dados mensais ja disponveis no PostgreSQL. |
| GeoJSON grande no PostgreSQL (PostGIS) | **Baixo** | Baixa | Usar tipo `geometry` nativo do PostGIS com indice GIST. Gerar GeoJSON via `ST_AsGeoJSON` sob demanda. Considerar simplificacao geometrica se necessario. |
| Falha de pipeline Airflow | **Medio** | Media | Configurar retries (3x com backoff exponencial). Alertas via email/Slack. Dados da execucao anterior permanecem validos no PostgreSQL (tabelas nao sao truncadas antes de confirmar novos dados). |
| Regressao de performance | **Alto** | Baixa | Load testing antes do cutover. Indices otimizados no PostgreSQL. Connection pooling configurado. Benchmark automatizado comparando NestJS vs FastAPI. |
| Inconsistencia de dados entre NestJS e FastAPI | **Alto** | Media | Trafego sombra com comparacao automatizada por 7+ dias. Golden file tests. DeepDiff com tolerancia para floats. |
| API RDE OData indisponivel durante ingestao | **Medio** | Media | Retry com backoff. Paginacao incremental (salvar checkpoint). Dados anteriores permanecem validos. |
| Perda de cache quente na migracao | **Baixo** | Alta | Na nova arquitetura, cache nao e necessario (dados pre-computados). Primeira requisicao ja e rapida (<100ms). |
| Dependencia de horario de atualizacao dos dados | **Medio** | Baixa | Documentar SLA de frescor (dados atualizados ate 08:00 UTC). Configurar DAGs com horarios adequados considerando timezone das APIs fonte. |

---

## Testes e Validacao

### Testes de Contrato (Golden Files)

1. **Gravacao**: Executar todos os 34+ endpoints da API NestJS com parametros variados e salvar respostas como JSON
2. **Comparacao**: Executar mesmos requests contra FastAPI e comparar com `deepdiff`
3. **Automacao**: Integrar no CI/CD (executa a cada PR)

### Testes de Qualidade de Dados (dbt)

```yaml
# dbt tests aplicados a todas as tabelas gold
version: 2

models:
  - name: gold_comexstat_summary
    tests:
      - dbt_utils.expression_is_true:
          expression: "trade_balance = exports - imports"
      - dbt_utils.expression_is_true:
          expression: "trade_current = exports + imports"
    columns:
      - name: period
        tests:
          - not_null
      - name: exports
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "exports >= 0"
      - name: imports
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "imports >= 0"

  - name: gold_comexstat_partners
    columns:
      - name: country
        tests:
          - not_null
      - name: percentage
        tests:
          - dbt_utils.expression_is_true:
              expression: "percentage >= 0 AND percentage <= 100"

  - name: gold_comexstat_states_ranking
    columns:
      - name: rank
        tests:
          - not_null
          - unique
      - name: state
        tests:
          - not_null
          - unique
      - name: participation
        tests:
          - dbt_utils.expression_is_true:
              expression: "participation >= 0 AND participation <= 100"

  - name: gold_rde_todos_registros
    columns:
      - name: CodigoRDE
        tests:
          - not_null
      - name: Ano
        tests:
          - not_null
          - dbt_utils.expression_is_true:
              expression: "Ano >= 2011"
      - name: Mes
        tests:
          - not_null
          - dbt_utils.accepted_values:
              values: [1,2,3,4,5,6,7,8,9,10,11,12]
```

### Testes de Integracao (End-to-End)

```python
# tests/test_integration.py
import pytest
import httpx


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url="http://localhost:8000", timeout=30)


class TestComexStatIntegration:
    def test_summary_default(self, client):
        resp = client.get("/comexstat/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert "period" in body["data"]
        assert body["data"]["exports"] >= 0

    def test_summary_all_periods(self, client):
        for period in ["currentMonth", "yearToDate", "lastYear"]:
            resp = client.get("/comexstat/summary", params={"period": period})
            assert resp.status_code == 200
            assert resp.json()["success"] is True

    def test_summary_custom_period(self, client):
        resp = client.get("/comexstat/summary", params={
            "period": "custom",
            "periodFrom": "2023-01",
            "periodTo": "2023-06",
        })
        assert resp.status_code == 200

    def test_states_ranking_structure(self, client):
        resp = client.get(
            "/comexstat/national-comparison/states-ranking",
            params={"flow": "export", "from": "2023-01", "to": "2023-12"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert isinstance(data, list)
        assert len(data) > 0
        # Verificar ordenacao por rank
        ranks = [item["rank"] for item in data]
        assert ranks == sorted(ranks)

    def test_dashboard_combines_data(self, client):
        resp = client.get("/comexstat/dashboard")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "summary" in data
        assert "topExports" in data
        assert "topImports" in data
        assert "topPartners" in data


class TestRdeIntegration:
    def test_todos_registros_pagination(self, client):
        resp = client.get("/rde/todos-registros", params={"top": 5, "skip": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) <= 5

    def test_registros_ied_ordering(self, client):
        resp = client.get(
            "/rde/registros-ied",
            params={"top": 10, "orderAno": "asc", "orderMes": "asc"},
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        if len(data) >= 2:
            # Verificar ordenacao ascendente
            for i in range(1, len(data)):
                assert (data[i]["Ano"], data[i]["Mes"]) >= (
                    data[i - 1]["Ano"],
                    data[i - 1]["Mes"],
                )


class TestSigmineIntegration:
    @pytest.mark.parametrize(
        "layer",
        [
            "area-servidao",
            "arrendamento",
            "bloqueio",
            "ce",
            "protecao-fonte",
            "reservas-garimpeiras",
        ],
    )
    def test_layer_returns_geojson(self, client, layer):
        resp = client.get(f"/layers/{layer}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["type"] == "FeatureCollection"
        assert "features" in body
```

### Teste de Carga

```bash
# Usando k6 para load testing
k6 run --vus 50 --duration 5m load_test.js
```

```javascript
// load_test.js
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
    thresholds: {
        http_req_duration: ['p(99)<200'],  // p99 < 200ms
        http_req_failed: ['rate<0.01'],     // <1% erro
    },
};

export default function () {
    const endpoints = [
        '/comexstat/summary',
        '/comexstat/partners?flow=export&topN=10',
        '/comexstat/products?flow=export&topN=20',
        '/comexstat/timeseries?startYear=2020',
        '/comexstat/national-comparison/states-ranking?flow=export&from=2023-01&to=2023-12',
        '/rde/todos-registros?top=100',
        '/layers/ce',
        '/scm/processos?limit=50',
    ];

    const endpoint = endpoints[Math.floor(Math.random() * endpoints.length)];
    const res = http.get(`${BASE_URL}${endpoint}`);

    check(res, {
        'status is 200': (r) => r.status === 200,
        'response time < 200ms': (r) => r.timings.duration < 200,
    });

    sleep(0.1);
}
```

### Regressao Automatizada (7 dias)

Durante a Fase 4, executar comparacao automatizada 24/7:

```bash
# Cron job: a cada 15 minutos, comparar respostas
*/15 * * * * python /opt/scripts/compare_shadow_responses.py >> /var/log/shadow_compare.log 2>&1
```

---

## Cronograma Resumido

```
Semana    1    2    3    4    5    6    7    8    9    10   11   12
          |    |    |    |    |    |    |    |    |    |    |    |
Fase 1    ████████
Infra     PG   Airflow
          MinIO dbt
          CI/CD

Fase 2              ████████████████████
Pipelines           SCM  ComexStat      RDE
                                        Sigmine

Fase 3                        ████████████████
FastAPI                       SCM  ComexStat
                                   RDE  Sigmine

Fase 4                                  ████████████
Validacao                               Shadow Traffic
                                        Benchmarks
                                        Contract Tests

Fase 5                                            ████
Cutover                                           Switch
                                                  Monitor

Pos-Cutover                                            ████████
                                                       Hot Standby
                                                       Decom NestJS
```

**Legenda**:
- Semanas 1-2: Infraestrutura (PostgreSQL, Airflow, MinIO, dbt, CI/CD)
- Semanas 3-6: Pipelines de dados (SCM -> ComexStat -> RDE -> Sigmine)
- Semanas 5-7: API FastAPI (sobreposicao intencional com Fase 2)
- Semanas 7-9: Validacao paralela (shadow traffic, benchmarks, testes)
- Semana 10: Cutover
- Semanas 11-12: Estabilizacao e descomissionamento

---

## Checklist de Go/No-Go para Cutover

### Requisitos Obrigatorios (todos devem estar marcados)

- [ ] Todos os 34+ endpoints retornando respostas identicas ao NestJS
- [ ] Todos os pipelines Airflow executando com sucesso por 7+ dias consecutivos
- [ ] Todos os testes dbt passando (not_null, unique, accepted_values, relationships, expressions)
- [ ] Tempo de resposta p99 < 200ms para todos os endpoints
- [ ] Frescor de dados dentro do SLA (atualizacao diaria completada)
- [ ] Zero divergencias no trafego sombra por 48h consecutivas
- [ ] Taxa de erro < 0.1% por 48h consecutivas
- [ ] Monitoramento e alertas configurados e testados
- [ ] Procedimento de rollback documentado e testado
- [ ] Load test executado com sucesso (50 VUs, 5min, p99 < 200ms)
- [ ] Documentacao OpenAPI (Swagger) equivalente a atual
- [ ] Backup do PostgreSQL configurado e verificado

### Requisitos Desejaveis

- [ ] Logs centralizados configurados
- [ ] Dashboard de monitoramento criado (Grafana/CloudWatch)
- [ ] Runbook de operacao documentado
- [ ] Comunicacao enviada para stakeholders
- [ ] Plano de comunicacao para incidentes preparado

### Decisao

| Criterio | Status | Responsavel |
|----------|--------|-------------|
| Paridade funcional | Pendente | Engenharia |
| Performance | Pendente | Engenharia |
| Qualidade de dados | Pendente | Dados |
| Infra e monitoramento | Pendente | DevOps |
| **Decisao final** | **GO / NO-GO** | **Tech Lead** |
