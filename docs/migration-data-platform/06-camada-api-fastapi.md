# 06 - Design da Nova Camada de API (FastAPI)

Este documento descreve o design da nova API FastAPI que substituira a API NestJS atual, servindo dados pre-computados a partir do PostgreSQL.

---

## 1. Principio de Preservacao de Contrato

A migracao para FastAPI deve obedecer a uma regra fundamental: **preservacao total do contrato de API**.

- **Todos os parametros de requisicao** (query params, tipos, valores default, regras de validacao) devem permanecer **identicos** aos da API NestJS atual.
- **Todas as estruturas de resposta** (campos, tipos, aninhamentos) devem ser **identicas** campo a campo.
- Os clientes (frontends, integracoes, scripts) **nao devem perceber nenhuma mudanca** na interface.
- A unica mudanca e **interna**: em vez de chamar APIs externas (ComexStat, RDE OData, ANM) e agregar dados em memoria, a FastAPI consulta **tabelas pre-computadas no PostgreSQL** (camada gold).

### O que muda internamente

| Aspecto | NestJS (Atual) | FastAPI (Novo) |
|---------|---------------|----------------|
| Fonte de dados | APIs externas (HTTP) | PostgreSQL (tabelas gold) |
| Agregacao | Em memoria (JavaScript) | Pre-computada pelo dbt |
| Cache | cache-manager (TTL 24h) | Desnecessario (dados ja materializados) |
| Timeout | 60s por chamada externa | <100ms por query SQL |

---

## 2. Mapeamento Completo de Endpoints

### 2.1 ComexStat (9 endpoints)

#### 2.1.1 GET /comexstat/summary

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera dados do Quadro Resumo |
| **Query Params** | `period` (enum: `currentMonth`, `yearToDate`, `lastYear`, `custom`; default: `yearToDate`, opcional), `periodFrom` (string YYYY-MM, opcional), `periodTo` (string YYYY-MM, opcional) |
| **Validacao** | `period` deve ser um valor do enum `SummaryPeriod`. Quando `period=custom`, `periodFrom` e `periodTo` sao obrigatorios. |
| **Response DTO** | `SummaryResponseDto` |
| **Estrutura** | `{ success: bool, data: SummaryDataDto }` |
| **SummaryDataDto** | `period: string`, `exports: number`, `imports: number`, `tradeBalance: number`, `tradeCurrent: number`, `exportParticipation?: number`, `importParticipation?: number`, `exportRanking?: number`, `importRanking?: number` |
| **Tabela Gold** | `gold_comexstat_summary` |
| **SQL** | `SELECT * FROM gold_comexstat_summary WHERE period_type = :period AND period_from = :from AND period_to = :to` |

#### 2.1.2 GET /comexstat/summary-history

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera dados do Quadro Resumo para multiplos meses |
| **Query Params** | `from` (string YYYY-MM, **obrigatorio**), `to` (string YYYY-MM, **obrigatorio**) |
| **Validacao** | Ambos obrigatorios (`@IsNotEmpty`), formato YYYY-MM. Periodo inicial deve ser anterior ao final. |
| **Response DTO** | `SummaryHistoryResponseDto` |
| **Estrutura** | `{ success: bool, data: SummaryDataDto[] }` |
| **Tabela Gold** | `gold_comexstat_summary_history` |
| **SQL** | `SELECT * FROM gold_comexstat_summary_history WHERE month_key BETWEEN :from AND :to ORDER BY month_key` |

#### 2.1.3 GET /comexstat/timeseries

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera dados de series temporais |
| **Query Params** | `periodicity` (enum: `monthly`, `annual`; default: `monthly`, opcional), `series` (enum: `export`, `import`, `current`, `balance`; default: `current`, opcional), `startYear` (int, **obrigatorio**), `endYear` (int, opcional), `includeSectors` (bool, default: `false`, opcional) |
| **Validacao** | `startYear` obrigatorio, inteiro. `endYear` inteiro opcional (default: ano corrente). `includeSectors` transformado via `toBoolean`. |
| **Response DTO** | `TimeSeriesResponseDto` |
| **Estrutura** | `{ success: bool, data: TimeSeriesDataDto[] }` |
| **TimeSeriesDataDto** | `period: string`, `year?: string`, `month?: string`, `exports?: number`, `imports?: number`, `balance?: number`, `current?: number`, `sectors?: TimeSeriesSectorDto[]` |
| **TimeSeriesSectorDto** | `code: string`, `name: string`, `value: number` |
| **Tabela Gold** | `gold_comexstat_timeseries` |
| **SQL** | `SELECT * FROM gold_comexstat_timeseries WHERE year >= :startYear AND year <= :endYear AND periodicity = :periodicity` (com JOIN em `gold_comexstat_timeseries_sectors` se `includeSectors=true`) |

#### 2.1.4 GET /comexstat/partners

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera informacoes dos paises parceiros |
| **Query Params** | `flow` (enum: `export`, `import`, `current`; default: `current`, opcional), `period` (enum: `currentMonth`, `yearToDate`, `lastYear`, `custom`; default: `yearToDate`, opcional), `periodFrom` (string YYYY-MM, opcional), `periodTo` (string YYYY-MM, opcional), `topN` (int positivo, default: `10`, opcional) |
| **Validacao** | `topN` deve ser inteiro positivo. |
| **Response DTO** | `PartnerCountriesResponseDto` |
| **Estrutura** | `{ success: bool, data: PartnerCountryDto[] }` |
| **PartnerCountryDto** | `country: string`, `exports?: number`, `imports?: number`, `current?: number`, `balance?: number`, `percentage?: number` |
| **Tabela Gold** | `gold_comexstat_partners` |
| **SQL** | `SELECT * FROM gold_comexstat_partners WHERE flow = :flow AND period_type = :period ORDER BY value DESC LIMIT :topN` |

#### 2.1.5 GET /comexstat/products

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera os produtos mais negociados |
| **Query Params** | `flow` (enum: `export`, `import`; default: `export`, opcional), `periodicity` (enum: `monthly`, `annual`; default: `annual`, opcional), `year` (int, opcional), `periodFrom` (string YYYY-MM, opcional), `periodTo` (string YYYY-MM, opcional), `aggregation` (enum: `ncm`, `heading`, `chapter`; default: `heading`, opcional), `topN` (int positivo, default: `20`, opcional) |
| **Validacao** | `flow` restrito a `export` ou `import` (`@IsIn`). `topN` inteiro positivo. Logica de periodo: se `periodFrom`+`periodTo` fornecidos, usa periodo customizado; senao se `year` fornecido, usa ano; senao usa default (ano anterior para annual, year-to-date para monthly). |
| **Response DTO** | `TopProductsResponseDto` |
| **Estrutura** | `{ success: bool, data: ProductDto[] }` |
| **ProductDto** | `code: string`, `description: string`, `value: number`, `quantity?: number`, `weight?: number`, `percentage?: number` |
| **Tabela Gold** | `gold_comexstat_products` |
| **SQL** | `SELECT * FROM gold_comexstat_products WHERE flow = :flow AND aggregation = :aggregation AND period_from = :from AND period_to = :to ORDER BY value DESC LIMIT :topN` |

#### 2.1.6 GET /comexstat/national-comparison

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera participacao nacional e ranking do Ceara |
| **Query Params** | `flow` (enum: `export`, `import`; default: `export`, opcional), `from` (string YYYY-MM, **obrigatorio**), `to` (string YYYY-MM, **obrigatorio**) |
| **Validacao** | `flow` restrito a `export` ou `import`. `from` e `to` obrigatorios. |
| **Response DTO** | `NationalComparisonResponseDto` |
| **Estrutura** | `{ success: bool, data: NationalComparisonDto }` |
| **NationalComparisonDto** | `participation: number`, `ranking: number` |
| **Tabela Gold** | `gold_comexstat_national_comparison` |
| **SQL** | `SELECT participation, ranking FROM gold_comexstat_national_comparison WHERE flow = :flow AND period_from = :from AND period_to = :to` |

#### 2.1.7 GET /comexstat/national-comparison/states-ranking

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera ranking de todos os estados ordenado por valor |
| **Query Params** | `flow` (enum: `export`, `import`; default: `export`, opcional), `from` (string YYYY-MM, **obrigatorio**), `to` (string YYYY-MM, **obrigatorio**) |
| **Validacao** | Mesma validacao de `NationalComparisonQueryDto`. |
| **Response DTO** | `StatesRankingResponseDto` |
| **Estrutura** | `{ success: bool, data: StateRankingItemDto[] }` |
| **StateRankingItemDto** | `rank: number`, `state: string`, `value: number`, `participation: number`, `topSectors?: StateRankingSectorDto[]`, `topPartners?: StateRankingPartnerDto[]`, `topProducts?: StateRankingProductDto[]` |
| **StateRankingSectorDto** | `code: string`, `name: string`, `value: number`, `percentage: number` |
| **StateRankingPartnerDto** | `country: string`, `value: number`, `percentage: number` |
| **StateRankingProductDto** | `code: string`, `description: string`, `value: number`, `percentage: number` |
| **Tabela Gold** | `gold_comexstat_states_ranking` (com tabelas auxiliares `gold_comexstat_state_sectors`, `gold_comexstat_state_partners`, `gold_comexstat_state_products`) |
| **SQL** | Query principal + 3 JOINs para top 5 setores, parceiros e produtos por estado |

> **Nota**: Este e o endpoint mais pesado da API atual. Ele realiza 5 chamadas paralelas a API externa ComexStat, cada uma com timeout de 60s. Na nova arquitetura, sera uma unica query SQL.

#### 2.1.8 GET /comexstat/dashboard

| Item | Detalhe |
|------|---------|
| **Descricao** | Recupera dados consolidados do painel |
| **Query Params** | `year` (int, opcional; default: ano corrente) |
| **Validacao** | `year` inteiro opcional. |
| **Response DTO** | `DashboardResponseDto` |
| **Estrutura** | `{ success: bool, data: DashboardDataDto }` |
| **DashboardDataDto** | `summary: SummaryDataDto`, `topExports: ProductDto[]`, `topImports: ProductDto[]`, `topPartners: PartnerCountryDto[]` |
| **Tabela Gold** | Combina `gold_comexstat_summary`, `gold_comexstat_products`, `gold_comexstat_partners` |
| **SQL** | Multiplas queries reaproveitando os servicos de summary, products e partners |

#### 2.1.9 DELETE /comexstat/cache

| Item | Detalhe |
|------|---------|
| **Descricao** | Limpa o cache de dados do ComexStat |
| **Query Params** | Nenhum |
| **Response** | `{ success: bool, message: string }` |
| **Novo comportamento** | No-op (sem cache para limpar) ou trigger de re-processamento do pipeline |

### 2.2 RDE (2 endpoints)

#### 2.2.1 GET /rde/todos-registros

| Item | Detalhe |
|------|---------|
| **Descricao** | Consulta todos os registros RDE publicados (a partir de novembro de 2011) |
| **Query Params** | `skip` (int >= 0, opcional), `top` (int positivo, default: `100`, opcional), `orderAno` (enum: `asc`, `desc`; opcional, default implicitly `desc`), `orderMes` (enum: `asc`, `desc`; opcional, default implicitly `desc`) |
| **Validacao** | `top` inteiro positivo. `orderAno` e `orderMes` restritos a `asc`/`desc`. |
| **Response DTO** | `TodosRegistrosResponseDto` |
| **Estrutura** | `{ success: bool, data: TodosRegistrosDto[], total?: number }` |
| **TodosRegistrosDto** | `CodigoRDE: string`, `NomePessoaNacional?: string`, `UfPessoaNacional?: string`, `NomePessoaEstrangeira?: string`, `PaisPessoaEstrangeira?: string`, `MoedaOperacao?: string`, `ValorOperacao?: number`, `Sistema: string`, `Ocorrencia: string`, `Modalidade: string`, `Ano: number`, `Mes: number` |
| **Tabela Gold** | `gold_rde_todos_registros` |
| **SQL** | `SELECT * FROM gold_rde_todos_registros WHERE uf_pessoa_nacional LIKE '%CE%' ORDER BY ano :orderAno, mes :orderMes LIMIT :top OFFSET :skip` |

#### 2.2.2 GET /rde/registros-ied

| Item | Detalhe |
|------|---------|
| **Descricao** | Consulta registros RDE-IED com CNPJ Base da Receptora |
| **Query Params** | Mesmos de `todos-registros`: `skip`, `top`, `orderAno`, `orderMes` |
| **Response DTO** | `RegistrosIedResponseDto` |
| **Estrutura** | `{ success: bool, data: RegistrosIedDto[], total?: number }` |
| **RegistrosIedDto** | `CodigoRDE: string`, `CnpjBaseReceptora: string`, `NomePessoaNacional: string`, `UfPessoaNacional?: string`, `NomePessoaEstrangeira?: string`, `PaisPessoaEstrangeira?: string`, `MoedaOperacao?: string`, `ValorOperacao?: number`, `Sistema: string`, `Ocorrencia: string`, `Modalidade: string`, `Ano: number`, `Mes: number` |
| **Tabela Gold** | `gold_rde_registros_ied` |
| **SQL** | `SELECT * FROM gold_rde_registros_ied WHERE uf_pessoa_nacional LIKE '%CE%' ORDER BY ano :orderAno, mes :orderMes LIMIT :top OFFSET :skip` |

### 2.3 SCM - Sistema de Cadastro Mineiro (17 endpoints)

O modulo SCM ja utiliza banco de dados (SQLite via TypeORM). Na migracao, as entidades serao migradas para PostgreSQL.

| # | Metodo | Rota | Query Params | Descricao | Tabela PostgreSQL |
|---|--------|------|-------------|-----------|-------------------|
| 1 | GET | `/scm/health` | - | Status de saude do sistema | Verificacao de conexao |
| 2 | GET | `/scm/summary` | - | Resumo com contadores e analytics | Multiplas tabelas SCM |
| 3 | GET | `/scm/processos` | `limit` (number, opcional) | Todos os processos minerarios | `scm_processos` |
| 4 | GET | `/scm/fases` | - | Todas as fases dos processos | `scm_fases_processo` |
| 5 | GET | `/scm/tipos` | - | Todos os tipos de requerimento | `scm_tipos_requerimento` |
| 6 | GET | `/scm/municipios` | - | Todos os municipios | `scm_municipios` |
| 7 | GET | `/scm/substancias` | - | Todas as substancias/minerais | `scm_substancias` |
| 8 | GET | `/scm/analytics/by-fase` | - | Contagem de processos por fase | `scm_processos` JOIN `scm_fases_processo` |
| 9 | GET | `/scm/analytics/by-tipo` | - | Contagem de processos por tipo | `scm_processos` JOIN `scm_tipos_requerimento` |
| 10 | GET | `/scm/analytics/by-municipio` | - | Contagem de processos por municipio | `scm_processo_municipios` JOIN `scm_municipios` |
| 11 | GET | `/scm/analytics/by-substancia` | - | Contagem de processos por substancia | `scm_processo_substancias` JOIN `scm_substancias` |
| 12 | GET | `/scm/analytics/by-uf` | - | Contagem de processos por UF | `scm_municipios` (agrupado por SGUF) |
| 13 | GET | `/scm/relations/processo-municipios` | `processo` (string, opcional) | Relacionamentos processo-municipio | `scm_processo_municipios` |
| 14 | GET | `/scm/relations/processo-substancias` | `processo` (string, opcional) | Relacionamentos processo-substancia | `scm_processo_substancias` |
| 15 | POST | `/scm/update` | - | Dispara atualizacao manual dos dados | Trigger de pipeline Airflow |
| 16 | GET | `/scm/search` | `processo` (string), `municipio` (number), `substancia` (number), `fase` (number), `tipo` (number), `limit` (number) - todos opcionais | Busca de processos com filtros | `scm_processos` com JOINs condicionais |

#### Entidades SCM (TypeORM -> SQLAlchemy)

**Processo**: `DSProcesso` (PK, varchar), `NRProcesso`, `NRAnoProcesso`, `BTAtivo`, `NRNUP`, `IDTipoRequerimento` (FK), `IDFaseProcesso` (FK), `IDUnidadeAdministrativaRegional`, `IDUnidadeProtocolizadora`, `DTProtocolo`, `DTPrioridade`, `QTAreaHA`

**FaseProcesso**: `IDFaseProcesso` (PK), `DSFaseProcesso`

**TipoRequerimento**: `IDTipoRequerimento` (PK), `DSTipoRequerimento`

**Municipio**: `IDMunicipio` (PK), `NMMunicipio`, `SGUF`

**Substancia**: `IDSubstancia` (PK), `NMSubstancia`

**ProcessoMunicipio**: `DSProcesso` (FK), `IDMunicipio` (FK)

**ProcessoSubstancia**: `DSProcesso` (FK), `IDSubstancia` (FK), `IDTipoUsoSubstancia`, `IDMotivoEncerramentoSubstancia`

### 2.4 Sigmine / Layers (6 endpoints)

| # | Metodo | Rota | Query Params | Descricao | Tabela PostgreSQL |
|---|--------|------|-------------|-----------|-------------------|
| 1 | GET | `/layers/area-servidao` | - | GeoJSON de AREA_SERVIDAO | `gold_sigmine_layers` (PostGIS) |
| 2 | GET | `/layers/arrendamento` | - | GeoJSON de ARRENDAMENTO | `gold_sigmine_layers` |
| 3 | GET | `/layers/bloqueio` | - | GeoJSON de BLOQUEIO | `gold_sigmine_layers` |
| 4 | GET | `/layers/ce` | - | GeoJSON de CE (Processos Minerais) | `gold_sigmine_layers` |
| 5 | GET | `/layers/protecao-fonte` | - | GeoJSON de PROTECAO_FONTE | `gold_sigmine_layers` |
| 6 | GET | `/layers/reservas-garimpeiras` | - | GeoJSON de RESERVAS_GARIMPEIRAS | `gold_sigmine_layers` |

**Response**: `FeatureCollection<Geometry, GeoJsonProperties>` (padrao GeoJSON RFC 7946)

**Layers disponiveis** (enum `SigmineLayer`): `area-servidao`, `arrendamento`, `bloqueio`, `ce`, `protecao-fonte`, `reservas-garimpeiras`

Cada layer e carregada a partir de Shapefiles na API atual. Na nova arquitetura, os shapefiles serao convertidos para PostGIS e armazenados em `gold_sigmine_layers` com coluna `geometry` nativa.

---

## 3. Modelos Pydantic

Modelos Pydantic v2 equivalentes aos DTOs TypeScript atuais. Devem reproduzir **exatamente** a mesma estrutura de resposta.

### 3.1 ComexStat - Modelos de Resposta

```python
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ---- Enums ----

class SummaryPeriod(str, Enum):
    CURRENT_MONTH = "currentMonth"
    YEAR_TO_DATE = "yearToDate"
    LAST_YEAR = "lastYear"
    CUSTOM = "custom"


class TradeFlow(str, Enum):
    EXPORT = "export"
    IMPORT = "import"
    CURRENT = "current"


class TimeSeriesPeriodicity(str, Enum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class TimeSeriesSeries(str, Enum):
    EXPORT = "export"
    IMPORT = "import"
    CURRENT = "current"
    BALANCE = "balance"


class AggregationLevel(str, Enum):
    NCM = "ncm"
    HEADING = "heading"
    CHAPTER = "chapter"


# ---- Summary ----

class SummaryDataDto(BaseModel):
    period: str
    exports: float = Field(description="Valor em milhoes de dolares (M USD).")
    imports: float = Field(description="Valor em milhoes de dolares (M USD).")
    trade_balance: float = Field(
        alias="tradeBalance",
        description="Valor em milhoes de dolares (M USD).",
    )
    trade_current: float = Field(
        alias="tradeCurrent",
        description="Valor em milhoes de dolares (M USD).",
    )
    export_participation: Optional[float] = Field(
        None, alias="exportParticipation"
    )
    import_participation: Optional[float] = Field(
        None, alias="importParticipation"
    )
    export_ranking: Optional[float] = Field(None, alias="exportRanking")
    import_ranking: Optional[float] = Field(None, alias="importRanking")

    model_config = {"populate_by_name": True, "by_alias": True}


class SummaryResponseDto(BaseModel):
    success: bool
    data: SummaryDataDto


class SummaryHistoryResponseDto(BaseModel):
    success: bool
    data: list[SummaryDataDto]


# ---- Time Series ----

class TimeSeriesSectorDto(BaseModel):
    code: str
    name: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")


class TimeSeriesDataDto(BaseModel):
    period: str
    year: Optional[str] = None
    month: Optional[str] = None
    exports: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    imports: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    balance: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    current: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    sectors: Optional[list[TimeSeriesSectorDto]] = None


class TimeSeriesResponseDto(BaseModel):
    success: bool
    data: list[TimeSeriesDataDto]


# ---- Partners ----

class PartnerCountryDto(BaseModel):
    country: str
    exports: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    imports: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    current: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    balance: Optional[float] = Field(
        None, description="Valor em milhoes de dolares (M USD)."
    )
    percentage: Optional[float] = None


class PartnerCountriesResponseDto(BaseModel):
    success: bool
    data: list[PartnerCountryDto]


# ---- Products ----

class ProductDto(BaseModel):
    code: str
    description: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")
    quantity: Optional[float] = None
    weight: Optional[float] = None
    percentage: Optional[float] = None


class TopProductsResponseDto(BaseModel):
    success: bool
    data: list[ProductDto]


# ---- National Comparison ----

class NationalComparisonDto(BaseModel):
    participation: float
    ranking: int


class NationalComparisonResponseDto(BaseModel):
    success: bool
    data: NationalComparisonDto


# ---- States Ranking ----

class StateRankingSectorDto(BaseModel):
    code: str
    name: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")
    percentage: float


class StateRankingPartnerDto(BaseModel):
    country: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")
    percentage: float


class StateRankingProductDto(BaseModel):
    code: str
    description: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")
    percentage: float


class StateRankingItemDto(BaseModel):
    rank: int
    state: str
    value: float = Field(description="Valor em milhoes de dolares (M USD).")
    participation: float
    top_sectors: Optional[list[StateRankingSectorDto]] = Field(
        None, alias="topSectors"
    )
    top_partners: Optional[list[StateRankingPartnerDto]] = Field(
        None, alias="topPartners"
    )
    top_products: Optional[list[StateRankingProductDto]] = Field(
        None, alias="topProducts"
    )

    model_config = {"populate_by_name": True, "by_alias": True}


class StatesRankingResponseDto(BaseModel):
    success: bool
    data: list[StateRankingItemDto]


# ---- Dashboard ----

class DashboardDataDto(BaseModel):
    summary: SummaryDataDto
    top_exports: list[ProductDto] = Field(alias="topExports")
    top_imports: list[ProductDto] = Field(alias="topImports")
    top_partners: list[PartnerCountryDto] = Field(alias="topPartners")

    model_config = {"populate_by_name": True, "by_alias": True}


class DashboardResponseDto(BaseModel):
    success: bool
    data: DashboardDataDto
```

### 3.2 RDE - Modelos de Resposta

```python
from pydantic import BaseModel, Field
from typing import Optional


class TodosRegistrosDto(BaseModel):
    codigo_rde: str = Field(alias="CodigoRDE")
    nome_pessoa_nacional: Optional[str] = Field(None, alias="NomePessoaNacional")
    uf_pessoa_nacional: Optional[str] = Field(None, alias="UfPessoaNacional")
    nome_pessoa_estrangeira: Optional[str] = Field(
        None, alias="NomePessoaEstrangeira"
    )
    pais_pessoa_estrangeira: Optional[str] = Field(
        None, alias="PaisPessoaEstrangeira"
    )
    moeda_operacao: Optional[str] = Field(None, alias="MoedaOperacao")
    valor_operacao: Optional[float] = Field(None, alias="ValorOperacao")
    sistema: str = Field(alias="Sistema")
    ocorrencia: str = Field(alias="Ocorrencia")
    modalidade: str = Field(alias="Modalidade")
    ano: int = Field(alias="Ano")
    mes: int = Field(alias="Mes")

    model_config = {"populate_by_name": True, "by_alias": True}


class RegistrosIedDto(BaseModel):
    codigo_rde: str = Field(alias="CodigoRDE")
    cnpj_base_receptora: str = Field(alias="CnpjBaseReceptora")
    nome_pessoa_nacional: str = Field(alias="NomePessoaNacional")
    uf_pessoa_nacional: Optional[str] = Field(None, alias="UfPessoaNacional")
    nome_pessoa_estrangeira: Optional[str] = Field(
        None, alias="NomePessoaEstrangeira"
    )
    pais_pessoa_estrangeira: Optional[str] = Field(
        None, alias="PaisPessoaEstrangeira"
    )
    moeda_operacao: Optional[str] = Field(None, alias="MoedaOperacao")
    valor_operacao: Optional[float] = Field(None, alias="ValorOperacao")
    sistema: str = Field(alias="Sistema")
    ocorrencia: str = Field(alias="Ocorrencia")
    modalidade: str = Field(alias="Modalidade")
    ano: int = Field(alias="Ano")
    mes: int = Field(alias="Mes")

    model_config = {"populate_by_name": True, "by_alias": True}


class TodosRegistrosResponseDto(BaseModel):
    success: bool
    data: list[TodosRegistrosDto]
    total: Optional[int] = None


class RegistrosIedResponseDto(BaseModel):
    success: bool
    data: list[RegistrosIedDto]
    total: Optional[int] = None
```

### 3.3 Modelos de Query (Validacao de Parametros)

```python
from fastapi import Query as QueryParam
from typing import Optional, Literal


# ComexStat Query Models (usados como dependencias nos routers)

class SummaryQuery:
    def __init__(
        self,
        period: Optional[SummaryPeriod] = QueryParam(
            default=SummaryPeriod.YEAR_TO_DATE
        ),
        periodFrom: Optional[str] = QueryParam(
            default=None, alias="periodFrom", pattern=r"^\d{4}-(0[1-9]|1[0-2])$"
        ),
        periodTo: Optional[str] = QueryParam(
            default=None, alias="periodTo", pattern=r"^\d{4}-(0[1-9]|1[0-2])$"
        ),
    ):
        self.period = period
        self.period_from = periodFrom
        self.period_to = periodTo


class SummaryHistoryQuery:
    def __init__(
        self,
        from_: str = QueryParam(alias="from", pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
        to: str = QueryParam(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    ):
        self.from_ = from_
        self.to = to


class TimeSeriesQuery:
    def __init__(
        self,
        startYear: int = QueryParam(alias="startYear"),
        periodicity: Optional[TimeSeriesPeriodicity] = QueryParam(
            default=TimeSeriesPeriodicity.MONTHLY
        ),
        series: Optional[TimeSeriesSeries] = QueryParam(
            default=TimeSeriesSeries.CURRENT
        ),
        endYear: Optional[int] = QueryParam(default=None, alias="endYear"),
        includeSectors: Optional[bool] = QueryParam(
            default=False, alias="includeSectors"
        ),
    ):
        self.start_year = startYear
        self.periodicity = periodicity
        self.series = series
        self.end_year = endYear
        self.include_sectors = includeSectors


class PartnerCountriesQuery:
    def __init__(
        self,
        flow: Optional[TradeFlow] = QueryParam(default=TradeFlow.CURRENT),
        period: Optional[SummaryPeriod] = QueryParam(
            default=SummaryPeriod.YEAR_TO_DATE
        ),
        periodFrom: Optional[str] = QueryParam(default=None, alias="periodFrom"),
        periodTo: Optional[str] = QueryParam(default=None, alias="periodTo"),
        topN: Optional[int] = QueryParam(default=10, ge=1, alias="topN"),
    ):
        self.flow = flow
        self.period = period
        self.period_from = periodFrom
        self.period_to = periodTo
        self.top_n = topN


class TopProductsQuery:
    def __init__(
        self,
        flow: Optional[Literal["export", "import"]] = QueryParam(default="export"),
        periodicity: Optional[TimeSeriesPeriodicity] = QueryParam(
            default=TimeSeriesPeriodicity.ANNUAL
        ),
        year: Optional[int] = QueryParam(default=None),
        periodFrom: Optional[str] = QueryParam(default=None, alias="periodFrom"),
        periodTo: Optional[str] = QueryParam(default=None, alias="periodTo"),
        aggregation: Optional[AggregationLevel] = QueryParam(
            default=AggregationLevel.HEADING
        ),
        topN: Optional[int] = QueryParam(default=20, ge=1, alias="topN"),
    ):
        self.flow = flow
        self.periodicity = periodicity
        self.year = year
        self.period_from = periodFrom
        self.period_to = periodTo
        self.aggregation = aggregation
        self.top_n = topN


class NationalComparisonQuery:
    def __init__(
        self,
        flow: Optional[Literal["export", "import"]] = QueryParam(default="export"),
        from_: str = QueryParam(alias="from"),
        to: str = QueryParam(),
    ):
        self.flow = flow
        self.from_ = from_
        self.to = to


class RdeQuery:
    def __init__(
        self,
        skip: Optional[int] = QueryParam(default=None, ge=0),
        top: Optional[int] = QueryParam(default=100, ge=1),
        orderAno: Optional[Literal["asc", "desc"]] = QueryParam(
            default=None, alias="orderAno"
        ),
        orderMes: Optional[Literal["asc", "desc"]] = QueryParam(
            default=None, alias="orderMes"
        ),
    ):
        self.skip = skip
        self.top = top
        self.order_ano = orderAno
        self.order_mes = orderMes
```

---

## 4. Estrutura do Projeto FastAPI

```
api/
├── main.py                          # App FastAPI, CORS, lifespan
├── config.py                        # Settings (DATABASE_URL, etc.)
├── database.py                      # Engine SQLAlchemy + async session
├── routers/
│   ├── __init__.py
│   ├── comexstat.py                 # 9 endpoints ComexStat
│   ├── rde.py                       # 2 endpoints RDE
│   ├── scm.py                       # 17 endpoints SCM
│   └── sigmine.py                   # 6 endpoints Sigmine/Layers
├── models/
│   ├── __init__.py
│   ├── comexstat.py                 # Pydantic response models ComexStat
│   ├── rde.py                       # Pydantic response models RDE
│   ├── scm.py                       # Pydantic response models SCM
│   └── sigmine.py                   # Pydantic response models Sigmine
├── schemas/
│   ├── __init__.py
│   └── database.py                  # SQLAlchemy ORM models (tabelas gold)
└── services/
    ├── __init__.py
    ├── comexstat.py                  # Queries PostgreSQL para ComexStat
    ├── rde.py                       # Queries PostgreSQL para RDE
    ├── scm.py                       # Queries PostgreSQL para SCM
    └── sigmine.py                   # Queries PostgreSQL para Sigmine
```

### Exemplo: main.py

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import engine
from .routers import comexstat, rde, scm, sigmine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verificar conexao com banco
    yield
    # Shutdown: fechar engine
    await engine.dispose()


app = FastAPI(
    title="ComexStat API",
    description="API de dados de comercio exterior do Ceara",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(comexstat.router, prefix="/comexstat", tags=["comexstat"])
app.include_router(rde.router, prefix="/rde", tags=["rde"])
app.include_router(scm.router, prefix="/scm", tags=["SCM - Sistema de Cadastro Mineiro"])
app.include_router(sigmine.router, prefix="/layers", tags=["layers"])
```

### Exemplo: routers/comexstat.py (endpoint summary)

```python
from fastapi import APIRouter, Depends
from ..models.comexstat import SummaryResponseDto, SummaryQuery
from ..services.comexstat import ComexStatService

router = APIRouter()


@router.get("/summary", response_model=SummaryResponseDto)
async def get_summary(
    query: SummaryQuery = Depends(),
    service: ComexStatService = Depends(),
):
    data = await service.get_summary_data(
        period_type=query.period,
        period_from=query.period_from,
        period_to=query.period_to,
    )
    return {"success": True, "data": data}
```

### Exemplo: services/comexstat.py (query PostgreSQL)

```python
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from ..database import get_session


class ComexStatService:
    def __init__(self, session: AsyncSession = Depends(get_session)):
        self.session = session

    async def get_summary_data(
        self,
        period_type: str,
        period_from: str | None = None,
        period_to: str | None = None,
    ) -> dict:
        query = text("""
            SELECT period, exports, imports, trade_balance, trade_current,
                   export_participation, import_participation,
                   export_ranking, import_ranking
            FROM gold_comexstat_summary
            WHERE period_type = :period_type
              AND (:period_from IS NULL OR period_from = :period_from)
              AND (:period_to IS NULL OR period_to = :period_to)
        """)
        result = await self.session.execute(
            query,
            {
                "period_type": period_type,
                "period_from": period_from,
                "period_to": period_to,
            },
        )
        row = result.fetchone()
        return dict(row._mapping) if row else {}
```

---

## 5. Comparacao de Performance

| Endpoint | Atual (NestJS) | Novo (FastAPI) | Ganho |
|----------|---------------|----------------|-------|
| `/comexstat/summary` | 2 chamadas HTTP paralelas (API ComexStat, timeout 60s) + agregacao em memoria → **2-10s** | 1 SELECT em tabela indexada → **<50ms** | **40-200x** |
| `/comexstat/summary-history` | 2 chamadas HTTP + mapeamento por mes → **5-15s** | 1 SELECT com range → **<50ms** | **100-300x** |
| `/comexstat/timeseries` | 1-2 chamadas HTTP + merge por periodo → **5-20s** | 1 SELECT + JOIN opcional → **<100ms** | **50-200x** |
| `/comexstat/partners` | 1-2 chamadas HTTP + agregacao por pais → **5-15s** | 1 SELECT com ORDER BY + LIMIT → **<50ms** | **100-300x** |
| `/comexstat/products` | 1 chamada HTTP + agregacao + ordenacao → **3-10s** | 1 SELECT com filtros → **<50ms** | **60-200x** |
| `/comexstat/national-comparison` | 3 chamadas HTTP paralelas → **5-30s** | 1 SELECT pre-computado → **<30ms** | **100-1000x** |
| **`/comexstat/national-comparison/states-ranking`** | **5 chamadas HTTP paralelas** (nacional, estados, setores, parceiros, produtos) com **timeout 60s cada** + agregacao complexa em memoria → **10-60s** | **1 SELECT com 3 JOINs** em tabelas pre-computadas → **<100ms** | **100-600x** |
| `/comexstat/dashboard` | 4 chamadas HTTP paralelas (reusa summary + products + partners) → **5-30s** | 3-4 SELECTs simples → **<100ms** | **50-300x** |
| `/rde/todos-registros` | 1 chamada OData API externa → **2-10s** | 1 SELECT com paginacao → **<50ms** | **40-200x** |
| `/rde/registros-ied` | 1 chamada OData API externa → **2-10s** | 1 SELECT com paginacao → **<50ms** | **40-200x** |
| `/layers/*` | Leitura de Shapefile do disco + conversao → **1-5s** | SELECT PostGIS com ST_AsGeoJSON → **<200ms** | **5-25x** |
| `/scm/*` | Query SQLite local → **<500ms** | Query PostgreSQL → **<100ms** | **2-5x** |

### Destaque: states-ranking

O endpoint `/comexstat/national-comparison/states-ranking` e o caso mais critico:

**Hoje**: Executa 5 chamadas paralelas a API ComexStat, cada uma com timeout de 60 segundos. Depois agrega tudo em memoria: monta rankings, calcula participacoes, faz top-5 de setores/parceiros/produtos por estado. Tempo total: **10 a 60 segundos**.

**Novo**: Uma unica query SQL com JOINs em tabelas `gold_comexstat_states_ranking`, `gold_comexstat_state_sectors`, `gold_comexstat_state_partners`, `gold_comexstat_state_products`. Tudo pre-computado pelo dbt. Tempo total: **<100ms**.

---

## 6. Testes de Contrato

### 6.1 Estrategia

1. **Gravar respostas golden** da API NestJS atual para todos os 34+ endpoints com parametros variados
2. **Comparar campo a campo** com as respostas da API FastAPI
3. **Suite automatizada** de testes de contrato executada em CI/CD

### 6.2 Gravacao de Respostas Golden

```python
# scripts/record_golden_responses.py
import httpx
import json
from pathlib import Path

NESTJS_BASE = "http://localhost:3000"
GOLDEN_DIR = Path("tests/golden")
GOLDEN_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = [
    ("GET", "/comexstat/summary", {}),
    ("GET", "/comexstat/summary", {"period": "currentMonth"}),
    ("GET", "/comexstat/summary", {"period": "lastYear"}),
    ("GET", "/comexstat/summary", {
        "period": "custom", "periodFrom": "2023-01", "periodTo": "2023-06"
    }),
    ("GET", "/comexstat/summary-history", {"from": "2023-01", "to": "2023-06"}),
    ("GET", "/comexstat/timeseries", {"startYear": 2020, "endYear": 2023}),
    ("GET", "/comexstat/timeseries", {
        "startYear": 2020, "periodicity": "annual", "series": "balance"
    }),
    ("GET", "/comexstat/timeseries", {
        "startYear": 2023, "includeSectors": True
    }),
    ("GET", "/comexstat/partners", {"flow": "export", "topN": 5}),
    ("GET", "/comexstat/partners", {
        "period": "custom", "periodFrom": "2023-01",
        "periodTo": "2023-06", "flow": "current"
    }),
    ("GET", "/comexstat/products", {"flow": "export", "topN": 10}),
    ("GET", "/comexstat/products", {
        "flow": "import", "aggregation": "chapter",
        "periodFrom": "2023-01", "periodTo": "2023-06"
    }),
    ("GET", "/comexstat/national-comparison", {
        "flow": "export", "from": "2023-01", "to": "2023-12"
    }),
    ("GET", "/comexstat/national-comparison/states-ranking", {
        "flow": "export", "from": "2023-01", "to": "2023-12"
    }),
    ("GET", "/comexstat/dashboard", {}),
    ("GET", "/comexstat/dashboard", {"year": 2023}),
    ("GET", "/rde/todos-registros", {"top": 10}),
    ("GET", "/rde/registros-ied", {"top": 10, "orderAno": "asc"}),
    ("GET", "/layers/ce", {}),
    ("GET", "/layers/area-servidao", {}),
    # ... demais endpoints
]


def record():
    client = httpx.Client(base_url=NESTJS_BASE, timeout=120)
    for method, path, params in ENDPOINTS:
        resp = client.request(method, path, params=params)
        filename = (
            path.replace("/", "_").strip("_")
            + "_"
            + "_".join(f"{k}={v}" for k, v in sorted(params.items()))
            + ".json"
        )
        (GOLDEN_DIR / filename).write_text(
            json.dumps(resp.json(), ensure_ascii=False, indent=2)
        )
        print(f"Gravado: {filename} ({resp.status_code})")


if __name__ == "__main__":
    record()
```

### 6.3 Testes de Contrato com pytest

```python
# tests/test_contract.py
import json
import httpx
import pytest
from pathlib import Path
from deepdiff import DeepDiff

FASTAPI_BASE = "http://localhost:8000"
GOLDEN_DIR = Path("tests/golden")


def load_golden_files():
    """Carrega todos os arquivos golden para parametrizacao."""
    cases = []
    for golden_file in sorted(GOLDEN_DIR.glob("*.json")):
        cases.append(golden_file)
    return cases


@pytest.fixture(scope="session")
def client():
    return httpx.Client(base_url=FASTAPI_BASE, timeout=30)


@pytest.mark.parametrize("golden_file", load_golden_files())
def test_contract_matches_golden(client, golden_file):
    """Verifica que a resposta FastAPI e identica a resposta golden."""
    # Extrair metodo, path e params do nome do arquivo
    parts = golden_file.stem.split("_")
    # ... parsing logic ...

    golden = json.loads(golden_file.read_text())
    response = client.get(path, params=params)

    assert response.status_code == 200

    actual = response.json()

    # Comparacao profunda ignorando diferencas de precisao float
    diff = DeepDiff(
        golden,
        actual,
        significant_digits=6,
        ignore_order=False,
    )

    assert not diff, (
        f"Diferenca encontrada para {golden_file.name}:\n{diff.to_json(indent=2)}"
    )


class TestComexStatSummaryContract:
    """Testes de contrato especificos para /comexstat/summary."""

    def test_response_structure(self, client):
        resp = client.get("/comexstat/summary")
        assert resp.status_code == 200
        body = resp.json()

        assert "success" in body
        assert body["success"] is True
        assert "data" in body

        data = body["data"]
        assert "period" in data
        assert "exports" in data
        assert "imports" in data
        assert "tradeBalance" in data
        assert "tradeCurrent" in data
        assert isinstance(data["exports"], (int, float))
        assert isinstance(data["imports"], (int, float))

    def test_custom_period_requires_dates(self, client):
        resp = client.get("/comexstat/summary", params={"period": "custom"})
        assert resp.status_code == 400


class TestStatesRankingContract:
    """Testes de contrato para o endpoint mais complexo."""

    def test_response_structure(self, client):
        resp = client.get(
            "/comexstat/national-comparison/states-ranking",
            params={"flow": "export", "from": "2023-01", "to": "2023-12"},
        )
        assert resp.status_code == 200
        body = resp.json()

        assert body["success"] is True
        assert isinstance(body["data"], list)

        if body["data"]:
            item = body["data"][0]
            assert "rank" in item
            assert "state" in item
            assert "value" in item
            assert "participation" in item
            assert item["rank"] == 1

            # Verificar sub-listas opcionais
            if "topSectors" in item and item["topSectors"]:
                sector = item["topSectors"][0]
                assert "code" in sector
                assert "name" in sector
                assert "value" in sector
                assert "percentage" in sector

            if "topPartners" in item and item["topPartners"]:
                partner = item["topPartners"][0]
                assert "country" in partner
                assert "value" in partner
                assert "percentage" in partner

            if "topProducts" in item and item["topProducts"]:
                product = item["topProducts"][0]
                assert "code" in product
                assert "description" in product
                assert "value" in product
                assert "percentage" in product
```

### 6.4 Execucao dos Testes

```bash
# 1. Gravar golden responses (com NestJS rodando)
python scripts/record_golden_responses.py

# 2. Executar testes de contrato (com FastAPI rodando)
pytest tests/test_contract.py -v --tb=long

# 3. CI/CD: executar ambas APIs e comparar
docker compose up -d nestjs fastapi
pytest tests/test_contract.py -v
```
