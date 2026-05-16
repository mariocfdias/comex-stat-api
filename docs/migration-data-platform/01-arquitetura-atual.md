# 01 - Arquitetura Atual

## Visao Geral da Stack

| Componente           | Tecnologia / Versao          | Funcao                                                    |
|----------------------|------------------------------|-----------------------------------------------------------|
| Framework            | NestJS 11                    | Framework HTTP principal                                  |
| ORM                  | TypeORM 0.3                  | Acesso ao banco de dados SQLite (apenas modulo SCM)       |
| Banco de dados       | SQLite3                      | Armazena dados do SCM localmente em `data/scm.db`         |
| Cache                | cache-manager + Redis (opc.) | Cache de respostas com TTL de 24h                         |
| HTTP Client          | Axios                        | Requisicoes para APIs externas (ComexStat, BCB, ANM)      |
| Geo-processamento    | @turf/turf, shapefile        | Leitura de shapefiles e filtragem geografica              |
| Descompressao        | adm-zip                      | Extracao do ZIP de microdados do SCM                      |
| Agendamento          | @nestjs/schedule             | Cron jobs para atualizacao SCM e keepalive                |
| Documentacao API     | @nestjs/swagger              | Swagger/OpenAPI auto-gerado                               |

---

## Arquitetura de Modulos

```
AppModule
  |
  +-- CacheModule (global, Redis ou in-memory)
  +-- ScheduleModule
  +-- TypeOrmModule (SQLite: data/scm.db)
  |
  +-- ComexstatModule
  |     +-- ComexstatController  (7 endpoints GET + 1 DELETE)
  |     +-- ComexstatService     (logica de consulta + agregacao)
  |     +-- COMEXSTAT_HTTP_CLIENT (Axios -> api-comexstat.mdic.gov.br)
  |
  +-- RdeModule
  |     +-- RdeController        (2 endpoints GET)
  |     +-- RdeService           (consulta OData ao BCB)
  |     +-- RDE_HTTP_CLIENT      (Axios -> olinda.bcb.gov.br)
  |
  +-- ScmModule
  |     +-- ScmController        (15 endpoints GET + 1 POST)
  |     +-- ScmService           (consultas ao SQLite)
  |     +-- ScmCsvService        (download ZIP + parse CSV)
  |     +-- ScmSchedulerService  (cron diario as 2h)
  |     +-- ScmRepositoryService (insercoes em lote no SQLite)
  |     +-- Entities: Processo, FaseProcesso, TipoRequerimento,
  |                   Municipio, Substancia, ProcessoMunicipio,
  |                   ProcessoSubstancia
  |
  +-- SigmineModule
  |     +-- SigmineController         (6 endpoints GET)
  |     +-- SigmineService            (leitura de shapefiles)
  |     +-- GeographicFilterService   (filtro por bounding box do Ceara)
  |
  +-- KeepaliveScheduler (ping a cada 10 min)
```

---

## Fluxo de Dados por Modulo

### ComexStat

**Fluxo:** Controller -> Service -> API externa MDIC -> Agregacao em memoria -> Resposta

1. O controller recebe query params e valida com `ValidationPipe`
2. O service resolve o periodo usando o `PeriodStrategyFactory` (Strategy Pattern para `annual` ou `monthly`)
3. O service verifica o cache (`comexstat:{endpoint}:{serializedParams}`)
4. Em caso de cache miss, o service faz `POST` para `https://api-comexstat.mdic.gov.br/general` via Axios
5. A resposta bruta (`{data: {list: [...]}}`) e agregada em memoria:
   - Somas de `metricFOB`, `metricKG`, `metricCIF`
   - Agrupamento por pais, estado, setor ISIC, NCM/heading/chapter
   - Calculo de percentuais, rankings e saldos
6. O resultado e armazenado em cache (TTL 24h) e retornado

**Endpoints:**

| Rota                                         | Metodo | Descricao                                  |
|----------------------------------------------|--------|--------------------------------------------|
| `GET /comexstat/summary`                     | GET    | Quadro resumo (exp/imp/saldo/corrente)     |
| `GET /comexstat/summary-history`             | GET    | Historico mensal do resumo                 |
| `GET /comexstat/timeseries`                  | GET    | Series temporais com setores opcionais     |
| `GET /comexstat/partners`                    | GET    | Top N paises parceiros                     |
| `GET /comexstat/products`                    | GET    | Top N produtos (NCM/heading/chapter)       |
| `GET /comexstat/national-comparison`         | GET    | Participacao do CE no total nacional       |
| `GET /comexstat/national-comparison/states-ranking` | GET | Ranking de todos os estados          |
| `GET /comexstat/dashboard`                   | GET    | Dados consolidados do painel               |
| `DELETE /comexstat/cache`                    | DELETE | Limpa cache (debug)                        |

### RDE

**Fluxo:** Controller -> Service -> API OData do BCB -> Resposta direta

1. O controller recebe `RdeQueryDto` (skip, top, orderAno, orderMes)
2. O service constroi parametros OData: `$format=json`, `$filter=contains(UfPessoaNacional,'CE')`, `$orderby`, `$skip`, `$top`
3. Faz `GET` para `https://olinda.bcb.gov.br/olinda/servico/RDE_Publicacao/versao/v1/odata/TodosRegistros` ou `/RegistrosIED`
4. Retorna os dados diretamente (sem agregacao complexa)

**Endpoints:**

| Rota                     | Metodo | Descricao                                  |
|--------------------------|--------|--------------------------------------------|
| `GET /rde/todos-registros` | GET  | Todos os registros RDE do Ceara            |
| `GET /rde/registros-ied`   | GET  | Registros RDE-IED com CNPJ da receptora    |

### SCM

**Fluxo:** Cron/Manual -> Download ZIP -> Extracao -> Parse CSV -> Filtro Ceara -> Carga SQLite -> Consulta

1. O `ScmSchedulerService` dispara diariamente as 2h (America/Sao_Paulo)
2. O `ScmCsvService` faz download do ZIP de `https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip`
3. Extrai com `adm-zip` para `data/scm/extracted/microdados-scm/`
4. Faz parse de 7 arquivos TXT (separador `;`) em entidades TypeORM
5. Filtra processos vinculados a municipios do Ceara (`SGUF = 'CE'`)
6. Insere em lote no SQLite (`data/scm.db`) com `synchronize: true`
7. O controller consulta o SQLite via `ScmService`

**Endpoints:**

| Rota                                    | Metodo | Descricao                            |
|-----------------------------------------|--------|--------------------------------------|
| `GET /scm/health`                       | GET    | Status do banco e contadores         |
| `GET /scm/summary`                      | GET    | Resumo analitico dos dados           |
| `GET /scm/processos`                    | GET    | Lista de processos (com limit)       |
| `GET /scm/fases`                        | GET    | Tabela de fases                      |
| `GET /scm/tipos`                        | GET    | Tabela de tipos de requerimento      |
| `GET /scm/municipios`                   | GET    | Tabela de municipios do Ceara        |
| `GET /scm/substancias`                  | GET    | Tabela de substancias minerais       |
| `GET /scm/analytics/by-fase`            | GET    | Contagem por fase                    |
| `GET /scm/analytics/by-tipo`            | GET    | Contagem por tipo de requerimento    |
| `GET /scm/analytics/by-municipio`       | GET    | Contagem por municipio               |
| `GET /scm/analytics/by-substancia`      | GET    | Contagem por substancia              |
| `GET /scm/analytics/by-uf`              | GET    | Contagem por UF                      |
| `GET /scm/relations/processo-municipios` | GET   | Relacoes processo-municipio          |
| `GET /scm/relations/processo-substancias`| GET   | Relacoes processo-substancia         |
| `GET /scm/search`                       | GET    | Busca com filtros multiplos          |
| `POST /scm/update`                      | POST   | Disparo manual de atualizacao        |

### Sigmine

**Fluxo:** Controller -> Service -> Leitura de shapefile local -> Filtro geografico -> Resposta GeoJSON

1. O controller chama `sigmineService.getLayer(layer)`
2. O service verifica cache (`sigmine:layer:{layer}`)
3. Em cache miss, le o shapefile de `static/{LAYER}/{LAYER}.shp` usando a biblioteca `shapefile`
4. Para layers que nao sejam `CE`, aplica filtro geografico usando bounding box do Ceara (via `@turf/turf`)
5. Retorna `FeatureCollection` GeoJSON

**Endpoints:**

| Rota                          | Metodo | Descricao                        |
|-------------------------------|--------|----------------------------------|
| `GET /layers/area-servidao`   | GET    | GeoJSON de Area de Servidao      |
| `GET /layers/arrendamento`    | GET    | GeoJSON de Arrendamento          |
| `GET /layers/bloqueio`        | GET    | GeoJSON de Bloqueio              |
| `GET /layers/ce`              | GET    | GeoJSON de Processos Minerais CE |
| `GET /layers/protecao-fonte`  | GET    | GeoJSON de Protecao de Fonte     |
| `GET /layers/reservas-garimpeiras` | GET | GeoJSON de Reservas Garimpeiras |

---

## Estrategia de Cache

**Configuracao** (em `src/app.module.ts`):

- Se a variavel de ambiente `REDIS_URL` esta definida, usa `cache-manager-redis-yet` como store
- Caso contrario, usa cache em memoria do `cache-manager` (padrao)
- TTL global: **24 horas** (`60 * 60 * 24` segundos)
- Escopo: global (via `isGlobal: true` no `CacheModule`)

**Padrao de chave de cache:**

```
{namespace}:{endpoint}:{json-normalizado-dos-parametros}
```

Exemplos:
- `comexstat:summary:{"period":{"from":"2024-01","to":"2024-12"}}`
- `rde:todos-registros:{"orderAno":"desc","orderMes":"desc","top":100}`
- `sigmine:layer:ce`

**Codigo de normalizacao** -- as chaves do objeto sao ordenadas alfabeticamente antes da serializacao:

```typescript
private serializeForCache(value: unknown): string {
  const normalize = (input: unknown): unknown => {
    if (Array.isArray(input)) {
      return input.map((item) => normalize(item));
    }
    if (input && typeof input === 'object') {
      return Object.keys(input as Record<string, unknown>)
        .sort()
        .reduce((acc, key) => {
          const normalizedValue = normalize(
            (input as Record<string, unknown>)[key],
          );
          if (normalizedValue !== undefined) {
            acc[key] = normalizedValue;
          }
          return acc;
        }, {} as Record<string, unknown>);
    }
    return input;
  };
  return JSON.stringify(normalize(value));
}
```

---

## Banco de Dados

- **Motor:** SQLite3
- **Arquivo:** `data/scm.db`
- **ORM:** TypeORM 0.3 com `synchronize: true` (schema auto-gerado)
- **Uso:** Exclusivamente para dados do modulo SCM

**Tabelas:**

| Tabela               | Chave Primaria      | Descricao                                      |
|----------------------|---------------------|-------------------------------------------------|
| `processos`          | `DSProcesso` (PK)  | Processos minerarios                            |
| `fase_processos`     | `IDFaseProcesso`    | Tabela de dominio: fases do processo            |
| `tipo_requerimentos` | `IDTipoRequerimento`| Tabela de dominio: tipos de requerimento        |
| `municipios`         | `IDMunicipio`       | Municipios (filtrados para CE)                  |
| `substancias`        | `IDSubstancia`      | Substancias minerais                            |
| `processo_municipios`| Composta            | Relacao N:N processo-municipio                  |
| `processo_substancias`| Composta           | Relacao N:N processo-substancia                 |

---

## Agendamento (Scheduling)

1. **SCM Daily Update** -- `ScmSchedulerService`
   - Cron: `EVERY_DAY_AT_2AM` (timezone `America/Sao_Paulo`)
   - Acao: download do ZIP, extracao, parse dos CSVs, filtragem para Ceara, carga no SQLite

2. **Keepalive Ping** -- `KeepaliveScheduler`
   - Cron: `EVERY_10_MINUTES`
   - Acao: `GET` para `SELF_PING_URL` (evitar cold start em plataformas como Render/Railway)

---

## Deploy Docker

O Dockerfile usa **multi-stage build**:

1. **Estagio de build:** Node 20 slim + dependencias nativas (python3, make, g++, curl, unzip)
   - Faz `npm ci` e `npm run build`
   - **Pre-download dos dados SCM** durante o build (com fallback para download em runtime)
   - Prune das devDependencies
2. **Estagio de runtime:** Node 20 slim + ca-certificates
   - Copia `dist/`, `node_modules/`, `static/` e `data/`
   - Expoe porta 3000
   - Comando: `node dist/main`

---

## PROBLEMAS (Justificativa da Migracao)

### 1. `getStatesRanking()` -- 5 chamadas HTTP paralelas

O endpoint mais pesado da API faz **5 chamadas paralelas** para a API externa do MDIC, cada uma com timeout de 60 segundos. Se qualquer uma delas falhar ou demorar, toda a requisicao falha:

```typescript
// src/comexstat/comexstat.service.ts - getStatesRanking()
const [
  nationalResponse,
  statesResponse,
  sectorsResponse,
  partnersResponse,
  productsResponse,
] = await Promise.all([
  this.queryGeneral({
    flow, monthDetail: false, period,
    metrics: ['metricFOB'],
  }),
  this.queryGeneral({
    flow, monthDetail: false, period,
    details: ['state'],
    metrics: ['metricFOB'],
  }),
  this.queryGeneral({
    flow, monthDetail: false, period,
    details: ['state', 'ISICSection'],
    metrics: ['metricFOB'],
  }),
  this.queryGeneral({
    flow, monthDetail: false, period,
    details: ['state', 'country'],
    metrics: ['metricFOB'],
  }),
  this.queryGeneral({
    flow, monthDetail: false, period,
    details: ['state', 'heading'],
    metrics: ['metricFOB'],
  }),
]);
```

Apos receber as respostas, o servico faz **agregacao em memoria** para cada estado: agrupa setores, parceiros e produtos, calcula percentuais, ordena e retorna o top 5 de cada dimensao por estado. Isso acontece **a cada requisicao**.

### 2. Agregacoes em memoria a cada requisicao

A API externa do ComexStat retorna listas brutas. Todo calculo de soma, percentual, ranking e agrupamento e feito no Node.js:

```typescript
// Exemplo: agregacao de parceiros por estado (em memoria)
partnersResponse.data.list.forEach((item) => {
  const stateName = item.state ?? item.stateName ?? '';
  const country = item.country ?? item.countryName ?? '';
  const value = this.toMillions(item.metricFOB ?? 0);

  if (!partnersByState.has(stateName)) {
    partnersByState.set(stateName, []);
  }
  partnersByState.get(stateName)!.push({ country, value });
});
```

Para 27 estados, com dezenas de setores, centenas de paises e milhares de headings, isso consome memoria significativa.

### 3. Timeout de 60 segundos nas APIs externas

Cada chamada para a API do MDIC tem timeout de 60 segundos:

```typescript
// src/comexstat/comexstat.module.ts
axios.create({
  baseURL: 'https://api-comexstat.mdic.gov.br',
  timeout: 60_000,
  // ...
});
```

### 4. Download SCM com timeout de 10 minutos e 3 retentativas

O download do ZIP de microdados da ANM (~centenas de MB) tem configuracao de 10 minutos de timeout com logica de retry:

```typescript
// src/scm/scm-csv.service.ts
const response = await axios({
  method: 'GET',
  url: this.downloadUrl,
  responseType: 'stream',
  timeout: 600000, // 10 minutos
  // ...
});
// maxRetries = 3, com exponential backoff
```

### 5. Sigmine sem mecanismo de atualizacao automatica

Os shapefiles do Sigmine sao estaticos no diretorio `/static/`. Nao ha cron nem endpoint de atualizacao. Os dados ficam desatualizados ate um novo deploy.

### 6. Cache Redis opcional -- risco de OOM

Quando `REDIS_URL` nao esta definida, o cache opera em memoria do processo Node.js. Sob carga, com multiplas respostas de ranking de estados em cache (cada uma com dados de 27 estados x 3 dimensoes), o consumo de memoria pode exceder os limites do container:

```typescript
// src/app.module.ts
if (redisUrl) {
  // usa Redis
} else {
  return { ttl }; // fallback: cache em memoria
}
```

### 7. `getNationalComparison()` -- 3 chamadas paralelas

Similar ao ranking, a comparacao nacional faz 3 chamadas paralelas:

```typescript
const [nationalResponse, cearaResponse, statesResponse] =
  await Promise.all([
    this.queryGeneral({ flow, monthDetail: false, period, metrics: ['metricFOB'] }),
    this.queryGeneral({ flow, monthDetail: false, period,
      filters: [{ filter: 'state', values: [this.CEARA_STATE_ID] }],
      metrics: ['metricFOB'] }),
    this.queryGeneral({ flow, monthDetail: false, period,
      details: ['state'], metrics: ['metricFOB'] }),
  ]);
```

### 8. SQLite com `synchronize: true` em producao

O uso de `synchronize: true` do TypeORM em producao pode causar perda de dados em caso de alteracao de entidades:

```typescript
TypeOrmModule.forRoot({
  type: 'sqlite',
  database: 'data/scm.db',
  synchronize: true, // perigoso em producao
});
```
