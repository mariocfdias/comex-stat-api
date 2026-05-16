# 04 - Design dos Pipelines de Ingestao

## Visao Geral

Este documento detalha as 4 DAGs do Apache Airflow que substituem a logica de ingestao e agendamento atualmente implementada no NestJS. Cada DAG descreve: nome, schedule, tasks, dependencias, politica de retry e pseudocodigo.

---

## DAG 1: `dag_comexstat_ingestao`

**Substitui:** `ComexstatService.queryGeneral()` e todas as chamadas on-demand a API ComexStat.

**Objetivo:** Extrair todos os dados necessarios da API ComexStat para pre-computar os 9 endpoints da API (summary, summary-history, timeseries, partners, products, national-comparison, states-ranking, dashboard).

**Schedule:** `0 3 * * *` (diariamente as 3h BRT)

**Retry Policy:** 3 tentativas com intervalo de 10 minutos entre cada tentativa.

**Tags:** `comexstat`, `diario`, `ingestao`

### Tasks

| Task ID | Descricao | Upstream |
|---------|-----------|----------|
| `extract_export_data` | Extrai dados de exportacao da API ComexStat | - |
| `extract_import_data` | Extrai dados de importacao da API ComexStat | - |
| `store_bronze` | Salva respostas JSON brutas no MinIO (bronze) | `extract_export_data`, `extract_import_data` |
| `transform_silver` | Normaliza e converte para Parquet na camada silver | `store_bronze` |
| `compute_gold_summary` | Pre-computa resumo para todos os tipos de periodo | `transform_silver` |
| `compute_gold_timeseries` | Pre-computa series temporais mensais e anuais | `transform_silver` |
| `compute_gold_partners` | Pre-computa top parceiros por fluxo/periodo | `transform_silver` |
| `compute_gold_products` | Pre-computa top produtos por fluxo/periodicidade/agregacao | `transform_silver` |
| `compute_gold_national` | Pre-computa comparacao nacional e ranking de estados | `transform_silver` |
| `compute_gold_dashboard` | Pre-computa painel consolidado | `compute_gold_summary`, `compute_gold_partners`, `compute_gold_products` |
| `load_postgresql` | Carrega todas as tabelas gold no PostgreSQL | `compute_gold_summary`, `compute_gold_timeseries`, `compute_gold_partners`, `compute_gold_products`, `compute_gold_national`, `compute_gold_dashboard` |

### Grafo de Dependencias

```
extract_export_data ──┐
                      ├──> store_bronze ──> transform_silver ──┬──> compute_gold_summary ────────┐
extract_import_data ──┘                                        ├──> compute_gold_timeseries ─────┤
                                                               ├──> compute_gold_partners ───────┤
                                                               ├──> compute_gold_products ───────┤
                                                               ├──> compute_gold_national ───────┤
                                                               └──> compute_gold_dashboard ──────┤
                                                                     (depende de summary,        │
                                                                      partners, products)        │
                                                                                                 v
                                                                                         load_postgresql
```

### Pseudocodigo

#### `extract_export_data`

Replica a chamada `queryGeneral()` do `ComexstatService` com `flow=EXPORT`:

```python
def extract_export_data(**context):
    """
    Replica: ComexstatService.queryGeneral({ flow: 'export', ... })
    
    A API ComexStat aceita POST /general com os seguintes parametros:
    - flow: 'export' ou 'import'
    - monthDetail: boolean (true para series mensais)
    - period: { from: 'YYYY-MM', to: 'YYYY-MM' }
    - filters: [{ filter: 'state', values: [23] }]  # 23 = Ceara
    - details: ['state', 'country', 'ISICSection', 'heading', 'chapter', 'ncm']
    - metrics: ['metricFOB', 'metricKG']
    """
    
    COMEXSTAT_API_URL = "https://api-comexstat.mdic.gov.br/general"
    CEARA_STATE_ID = 23
    
    # Calculo de periodos (replica getCurrentDateInfo())
    # A API ComexStat tem delay de ~2 meses nos dados
    now = datetime.utcnow()
    reference = now.replace(day=1) - relativedelta(months=2)
    current_year = reference.year
    current_month = reference.month
    
    # Definir periodos a extrair
    previous_year = current_year - 1
    
    # Extrair com o maximo de detalhes para permitir todas as agregacoes
    extraction_configs = [
        {
            "name": "export_ceara_monthly_detail",
            "params": {
                "flow": "export",
                "monthDetail": True,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "filters": [{"filter": "state", "values": [CEARA_STATE_ID]}],
                "details": ["country", "ISICSection", "heading"],
                "metrics": ["metricFOB", "metricKG"]
            }
        },
        {
            "name": "export_all_states",
            "params": {
                "flow": "export",
                "monthDetail": False,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "details": ["state"],
                "metrics": ["metricFOB"]
            }
        },
        {
            "name": "export_states_sectors",
            "params": {
                "flow": "export",
                "monthDetail": False,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "details": ["state", "ISICSection"],
                "metrics": ["metricFOB"]
            }
        },
        {
            "name": "export_states_countries",
            "params": {
                "flow": "export",
                "monthDetail": False,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "details": ["state", "country"],
                "metrics": ["metricFOB"]
            }
        },
        {
            "name": "export_states_products",
            "params": {
                "flow": "export",
                "monthDetail": False,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "details": ["state", "heading"],
                "metrics": ["metricFOB"]
            }
        },
        {
            "name": "export_national_total",
            "params": {
                "flow": "export",
                "monthDetail": False,
                "period": {
                    "from": f"{previous_year}-01",
                    "to": f"{current_year}-{current_month:02d}"
                },
                "metrics": ["metricFOB"]
            }
        },
    ]
    
    results = {}
    for config in extraction_configs:
        response = requests.post(
            COMEXSTAT_API_URL,
            json=config["params"],
            params={"language": "pt"},
            timeout=120
        )
        response.raise_for_status()
        data = response.json()
        
        if not data.get("success"):
            raise AirflowException(
                f"ComexStat API retornou erro: {data.get('message')}"
            )
        
        results[config["name"]] = data
    
    # Passa para a proxima task via XCom
    context["ti"].xcom_push(key="export_data", value=results)
```

#### `extract_import_data`

Identico ao `extract_export_data`, mas com `flow=import` e metrica adicional `metricCIF`:

```python
def extract_import_data(**context):
    """
    Mesma estrutura do extract_export_data, mas com:
    - flow: 'import'
    - metrics: ['metricFOB', 'metricKG', 'metricCIF']
    
    A metricCIF so existe para importacoes (replica a logica atual
    em getSummaryData() que pede metricCIF apenas para import).
    """
    # ... mesmo padrao, com flow="import" e metricCIF adicional
```

#### `compute_gold_summary`

Replica `ComexstatService.getSummaryData()`:

```python
def compute_gold_summary(**context):
    """
    Replica: getSummaryData(periodType, customPeriod)
    
    Pre-computa para todos os SummaryPeriod:
    - CURRENT_MONTH: mes anterior ao reference date
    - YEAR_TO_DATE: janeiro ate mes atual
    - LAST_YEAR: ano anterior completo
    
    Calculo (do metodo original):
      exports = toMillions(exportResponse.metricFOB)
      imports = toMillions(importResponse.metricFOB)
      tradeBalance = exports - imports
      tradeCurrent = exports + imports
    """
    
    silver_df = read_parquet_from_minio("silver/comexstat/trade_data.parquet")
    
    for period_type in ["currentMonth", "yearToDate", "lastYear"]:
        period = resolve_period(period_type)
        
        filtered = silver_df[
            (silver_df["period"] >= period["from"]) &
            (silver_df["period"] <= period["to"]) &
            (silver_df["state_id"] == 23)  # CEARA_STATE_ID
        ]
        
        exports_fob = filtered[filtered["flow"] == "export"]["metricFOB"].sum()
        imports_fob = filtered[filtered["flow"] == "import"]["metricFOB"].sum()
        
        exports = round(exports_fob / 1_000_000, 2)  # toMillions()
        imports_val = round(imports_fob / 1_000_000, 2)
        
        summary = {
            "period_type": period_type,
            "period_label": format_period_label(period_type, period),
            "exports": exports,
            "imports": imports_val,
            "trade_balance": exports - imports_val,
            "trade_current": exports + imports_val,
        }
        
        write_to_gold("gold/comexstat/summary/", summary)
```

#### `compute_gold_national` (Mais complexo)

Replica `getStatesRanking()` - a operacao mais cara do sistema atual (5 chamadas paralelas):

```python
def compute_gold_national(**context):
    """
    Replica: getNationalComparison() e getStatesRanking()
    
    O metodo original getStatesRanking() faz 5 queries paralelas:
    1. Total nacional (sem filtro de estado)
    2. Valores por estado
    3. Setores por estado (state + ISICSection)
    4. Parceiros por estado (state + country) 
    5. Produtos por estado (state + heading)
    
    E depois agrega em JavaScript com Maps para montar:
    - Ranking de 27 estados
    - Top 5 setores por estado
    - Top 5 parceiros por estado
    - Top 5 produtos por estado
    - Participacao (%) de cada estado no total nacional
    """
    
    silver_df = read_parquet_from_minio("silver/comexstat/trade_data.parquet")
    
    for flow in ["export", "import"]:
        for period_type in ["currentMonth", "yearToDate", "lastYear"]:
            period = resolve_period(period_type)
            
            period_df = silver_df[
                (silver_df["period"] >= period["from"]) &
                (silver_df["period"] <= period["to"]) &
                (silver_df["flow"] == flow)
            ]
            
            # Total nacional
            national_total = period_df["metricFOB"].sum()
            
            # Valores por estado
            states_df = (
                period_df.groupby("state")["metricFOB"]
                .sum()
                .reset_index()
            )
            states_df = states_df.sort_values("metricFOB", ascending=False)
            states_df["rank"] = range(1, len(states_df) + 1)
            states_df["value"] = (states_df["metricFOB"] / 1_000_000).round(2)
            states_df["participation"] = (
                (states_df["metricFOB"] / national_total * 100)
                if national_total > 0
                else 0
            )
            
            # Top 5 setores por estado
            sectors_by_state = period_df.groupby(
                ["state", "ISICSection", "ISICSectionCode"]
            )["metricFOB"].sum()
            # ... rank e slice top 5 por estado
            
            # Top 5 parceiros por estado
            partners_by_state = period_df.groupby(
                ["state", "country"]
            )["metricFOB"].sum()
            # ... rank e slice top 5 por estado
            
            # Top 5 produtos por estado
            products_by_state = period_df.groupby(
                ["state", "headingCode", "heading"]
            )["metricFOB"].sum()
            # ... rank e slice top 5 por estado
            
            write_to_gold(
                f"gold/comexstat/states_ranking/{flow}/{period_type}/"
            )
```

---

## DAG 2: `dag_rde_ingestao`

**Substitui:** `RdeService.getTodosRegistros()` e `RdeService.getRegistrosIed()` com chamadas on-demand a API OData do Banco Central.

**Schedule:** `0 4 * * *` (diariamente as 4h BRT)

**Retry Policy:** 3 tentativas com intervalo de 5 minutos.

**Tags:** `rde`, `diario`, `ingestao`, `odata`

### Tasks

| Task ID | Descricao | Upstream |
|---------|-----------|----------|
| `extract_all_records` | Pagina por toda a API OData /TodosRegistros | - |
| `extract_ied_records` | Pagina por toda a API OData /RegistrosIED | - |
| `store_bronze` | Salva respostas JSON brutas no MinIO | `extract_all_records`, `extract_ied_records` |
| `transform_silver` | Normaliza e filtra para Parquet | `store_bronze` |
| `load_postgresql` | Upsert nas tabelas gold do PostgreSQL | `transform_silver` |

### Grafo de Dependencias

```
extract_all_records ──┐
                      ├──> store_bronze ──> transform_silver ──> load_postgresql
extract_ied_records ──┘
```

### Pseudocodigo

#### `extract_all_records`

Replica `RdeService.buildODataParams()` e a paginacao:

```python
def extract_all_records(**context):
    """
    Replica: RdeService.getTodosRegistros()
    
    A API OData do BCB aceita parametros:
    - $format: json
    - $filter: contains(UfPessoaNacional,'CE')  # Filtro Ceara
    - $orderby: Ano desc,Mes desc
    - $skip: offset para paginacao
    - $top: tamanho da pagina
    
    O servico atual NAO faz paginacao completa - apenas retorna
    uma pagina por vez. Na nova plataforma, ingerimos TUDO.
    """
    
    RDE_BASE_URL = (
        "https://olinda.bcb.gov.br/olinda/servico/RDE/versao/v1/odata"
    )
    PAGE_SIZE = 1000
    
    all_records = []
    skip = 0
    
    while True:
        params = {
            "$format": "json",
            "$filter": "contains(UfPessoaNacional,'CE')",
            "$orderby": "Ano desc,Mes desc",
            "$skip": str(skip),
            "$top": str(PAGE_SIZE),
        }
        
        response = requests.get(
            f"{RDE_BASE_URL}/TodosRegistros",
            params=params,
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        records = data.get("value", [])
        
        if not records:
            break
        
        all_records.extend(records)
        skip += PAGE_SIZE
        
        logging.info(
            f"Pagina {skip // PAGE_SIZE}: "
            f"{len(records)} registros extraidos"
        )
    
    logging.info(
        f"Total extraido: {len(all_records)} registros de TodosRegistros"
    )
    context["ti"].xcom_push(key="todos_registros", value=all_records)
```

#### `extract_ied_records`

Mesmo padrao, com endpoint `/RegistrosIED`:

```python
def extract_ied_records(**context):
    """
    Replica: RdeService.getRegistrosIed()
    Mesmo padrao de paginacao, endpoint /RegistrosIED
    
    Campos retornados (RegistrosIedDto):
    - CodigoRDE, CnpjBaseReceptora, NomePessoaNacional
    - UfPessoaNacional, NomePessoaEstrangeira, PaisPessoaEstrangeira
    - MoedaOperacao, ValorOperacao, Sistema, Ocorrencia, Modalidade
    - Ano, Mes
    """
    # ... mesmo padrao com endpoint "/RegistrosIED"
```

#### `load_postgresql`

```python
def load_postgresql(**context):
    """
    Upsert dos dados no PostgreSQL.
    
    Tabelas destino:
    - gold_rde_todos_registros (PK: CodigoRDE + Ano + Mes)
    - gold_rde_registros_ied (PK: CodigoRDE + Ano + Mes)
    
    Estrategia: TRUNCATE + INSERT (dados completos, nao incrementais)
    """
    
    engine = create_engine(POSTGRES_CONN_STRING)
    
    todos_df = pd.DataFrame(
        context["ti"].xcom_pull(key="silver_todos")
    )
    ied_df = pd.DataFrame(
        context["ti"].xcom_pull(key="silver_ied")
    )
    
    with engine.begin() as conn:
        conn.execute("TRUNCATE TABLE gold_rde_todos_registros")
        todos_df.to_sql(
            "gold_rde_todos_registros", conn,
            if_exists="append", index=False
        )
        
        conn.execute("TRUNCATE TABLE gold_rde_registros_ied")
        ied_df.to_sql(
            "gold_rde_registros_ied", conn,
            if_exists="append", index=False
        )
```

---

## DAG 3: `dag_scm_ingestao`

**Substitui:** `ScmSchedulerService.handleDailyDataUpdate()`, `ScmCsvService.downloadAndExtractData()`, `ScmCsvService.loadDataToDatabase()`, e `ScmCsvService.filterDataForCeara()`.

**Schedule:** `0 2 * * *` (diariamente as 2h BRT - igual ao `@Cron(CronExpression.EVERY_DAY_AT_2AM)` atual)

**Retry Policy:** 3 tentativas com backoff exponencial (1min, 2min, 4min) - replica a logica atual em `downloadAndExtractData()` com `Math.pow(2, attempt - 1)`.

**Tags:** `scm`, `diario`, `ingestao`, `anm`

### Tasks

| Task ID | Descricao | Upstream |
|---------|-----------|----------|
| `check_freshness` | Sensor: verifica se dados precisam de atualizacao (threshold 48h) | - |
| `download_zip` | Baixa ZIP de microdados do site da ANM | `check_freshness` |
| `extract_csvs` | Extrai ZIP e armazena CSVs individuais no MinIO bronze | `download_zip` |
| `parse_and_filter` | Parseia TXTs delimitados por `;` e filtra para municipios do Ceara | `extract_csvs` |
| `load_reference_tables` | Carrega FaseProcesso, TipoRequerimento, Municipio, Substancia | `parse_and_filter` |
| `load_main_tables` | Carrega Processo, ProcessoMunicipio, ProcessoSubstancia (chunks de 500) | `load_reference_tables` |
| `compute_analytics` | Pre-computa agregacoes by-fase, by-tipo, by-municipio, by-substancia, by-uf | `load_main_tables` |

### Grafo de Dependencias

```
check_freshness ──> download_zip ──> extract_csvs ──> parse_and_filter
    ──> load_reference_tables ──> load_main_tables ──> compute_analytics
```

### Pseudocodigo

#### `check_freshness`

Replica `ScmCsvService.isDataFresh()`:

```python
class ScmFreshnessSensor(BaseSensorOperator):
    """
    Replica: ScmCsvService.isDataFresh()
    
    Logica original:
    - Verifica se o arquivo Processo.txt existe
    - Verifica se a idade do arquivo e menor que 48 horas
    - Se fresco, pula o download (retorna True para short-circuit)
    
    Na nova plataforma:
    - Verifica o timestamp do ultimo objeto bronze/scm/ no MinIO
    - Se < 48h, marca a DAG como skipped
    """
    
    MAX_AGE_HOURS = 48
    
    def poke(self, context):
        minio_client = get_minio_client()
        
        try:
            # Verifica o objeto mais recente na camada bronze do SCM
            latest_object = minio_client.stat_object(
                "datalake",
                "bronze/scm/latest/Processo.txt"
            )
            
            file_age_hours = (
                (datetime.utcnow() - latest_object.last_modified)
                .total_seconds() / 3600
            )
            
            if file_age_hours < self.MAX_AGE_HOURS:
                logging.info(
                    f"Dados SCM tem {file_age_hours:.0f}h "
                    f"(fresco, pulando download)"
                )
                raise AirflowSkipException("Dados ainda frescos")
            
            return True  # Dados antigos, continuar pipeline
            
        except Exception:
            return True  # Sem dados, continuar pipeline
```

#### `download_zip`

Replica `ScmCsvService.downloadAndExtractData()`:

```python
def download_zip(**context):
    """
    Replica: ScmCsvService.downloadAndExtractData()
    
    URL original:
        https://app.anm.gov.br/dadosabertos/SCM/microdados/microdados-scm.zip
    
    Configuracao original:
    - maxRetries: 3
    - Backoff exponencial: Math.min(1000 * Math.pow(2, attempt-1), 30000)
    - Timeout total: 600000ms (10 minutos)
    - HTTPS com rejectUnauthorized: false
    - Headers: User-Agent simulando navegador
    
    Na nova plataforma:
    - Retry e gerenciado pelo Airflow (retries=3, retry_delay
      com exponential backoff)
    - O arquivo e salvo diretamente no MinIO (nao no filesystem local)
    """
    
    DOWNLOAD_URL = (
        "https://app.anm.gov.br/dadosabertos/SCM/"
        "microdados/microdados-scm.zip"
    )
    
    response = requests.get(
        DOWNLOAD_URL,
        timeout=600,
        verify=False,  # rejectUnauthorized: false
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            ),
            "Accept": "application/zip, */*",
        },
        stream=True,
    )
    response.raise_for_status()
    
    # Salva diretamente no MinIO
    execution_date = context["ds"]
    minio_path = (
        f"bronze/scm/"
        f"ano={execution_date[:4]}/"
        f"mes={execution_date[5:7]}/"
        f"dia={execution_date[8:10]}/"
        f"microdados-scm.zip"
    )
    
    minio_client = get_minio_client()
    minio_client.put_object(
        "datalake", minio_path, response.raw,
        length=-1, part_size=10*1024*1024
    )
    
    context["ti"].xcom_push(key="zip_path", value=minio_path)
```

#### `parse_and_filter`

Replica `ScmCsvService.filterDataForCeara()` - a logica central de filtragem:

```python
def parse_and_filter(**context):
    """
    Replica: ScmCsvService.filterDataForCeara()
    
    LOGICA ORIGINAL DE FILTRAGEM DO CEARA:
    
    1. Filtrar municipios onde SGUF = 'CE'
       municipiosCE = municipios.filter(m => m.SGUF === 'CE')
    
    2. Criar set de IDs dos municipios do Ceara
       municipiosCEIds = Set(municipiosCE.map(m => m.IDMunicipio))
    
    3. Filtrar relacoes processo-municipio para municipios do Ceara
       processoMunicipiosCE = processoMunicipios.filter(
           pm => municipiosCEIds.has(pm.IDMunicipio)
       )
    
    4. Extrair IDs de processos que estao no Ceara
       processosIdsNoceara = Set(
           processoMunicipiosCE.map(pm => pm.DSProcesso)
       )
    
    5. Filtrar processos do Ceara
       processosCE = processos.filter(
           p => processosIdsNoceara.has(p.DSProcesso)
       )
    
    6. Filtrar substancias usadas no Ceara
       processoSubstanciasCE = processoSubstancias.filter(
           ps => processosIdsNoceara.has(ps.DSProcesso)
       )
       substanciasIdsNoceara = Set(
           processoSubstanciasCE.map(ps => ps.IDSubstancia)
       )
       substanciasCE = substancias.filter(
           s => substanciasIdsNoceara.has(s.IDSubstancia)
       )
    
    7. Tabelas de referencia (fases e tipos) sao mantidas
       integralmente (tabelas pequenas)
    
    FORMATO DOS ARQUIVOS:
    - Delimitador: ponto-e-virgula (;)
    - Primeira linha: cabecalho (ignorada)
    - Encoding: UTF-8
    """
    
    # Ler CSVs do MinIO bronze
    municipios_df = read_scm_csv(
        "Municipio.txt",
        ["IDMunicipio", "NMMunicipio", "SGUF"]
    )
    processos_df = read_scm_csv("Processo.txt", [
        "DSProcesso", "NRProcesso", "NRAnoProcesso",
        "BTAtivo", "NRNUP", "IDTipoRequerimento",
        "IDFaseProcesso", "IDUnidadeAdministrativaRegional",
        "IDUnidadeProtocolizadora", "DTProtocolo",
        "DTPrioridade", "QTAreaHA"
    ])
    processo_municipio_df = read_scm_csv(
        "ProcessoMunicipio.txt",
        ["DSProcesso", "IDMunicipio"]
    )
    processo_substancia_df = read_scm_csv(
        "ProcessoSubstancia.txt", [
            "DSProcesso", "IDSubstancia",
            "IDTipoUsoSubstancia",
            "IDMotivoEncerramentoSubstancia"
        ]
    )
    substancias_df = read_scm_csv(
        "Substancia.txt",
        ["IDSubstancia", "NMSubstancia"]
    )
    fases_df = read_scm_csv(
        "FaseProcesso.txt",
        ["IDFaseProcesso", "DSFaseProcesso"]
    )
    tipos_df = read_scm_csv(
        "TipoRequerimento.txt",
        ["IDTipoRequerimento", "DSTipoRequerimento"]
    )
    
    # === REPLICACAO EXATA DA LOGICA filterDataForCeara() ===
    
    # Passo 1: Municipios do Ceara
    municipios_ce = municipios_df[municipios_df["SGUF"] == "CE"]
    municipios_ce_ids = set(municipios_ce["IDMunicipio"].values)
    
    # Passo 2: Relacoes processo-municipio no Ceara
    pm_ce = processo_municipio_df[
        processo_municipio_df["IDMunicipio"].isin(municipios_ce_ids)
    ]
    
    # Passo 3: IDs de processos no Ceara
    processos_ids_ceara = set(pm_ce["DSProcesso"].values)
    
    # Passo 4: Processos do Ceara
    processos_ce = processos_df[
        processos_df["DSProcesso"].isin(processos_ids_ceara)
    ]
    
    # Passo 5: Substancias do Ceara
    ps_ce = processo_substancia_df[
        processo_substancia_df["DSProcesso"].isin(processos_ids_ceara)
    ]
    substancias_ids_ceara = set(ps_ce["IDSubstancia"].values)
    substancias_ce = substancias_df[
        substancias_df["IDSubstancia"].isin(substancias_ids_ceara)
    ]
    
    # Passo 6: Tabelas de referencia (mantidas integralmente)
    # fases_df e tipos_df nao sao filtrados (tabelas pequenas)
    
    # === DEDUPLICACAO (replica removeDuplicates*()) ===
    processos_ce = processos_ce.drop_duplicates(subset=["DSProcesso"])
    pm_ce = pm_ce.drop_duplicates(
        subset=["DSProcesso", "IDMunicipio"]
    )
    ps_ce = ps_ce.drop_duplicates(
        subset=["DSProcesso", "IDSubstancia"]
    )
    
    # Salvar como Parquet no MinIO silver
    save_parquet_to_minio(
        processos_ce, "silver/scm/processos.parquet"
    )
    save_parquet_to_minio(
        municipios_ce, "silver/scm/municipios.parquet"
    )
    save_parquet_to_minio(
        substancias_ce, "silver/scm/substancias.parquet"
    )
    save_parquet_to_minio(
        pm_ce, "silver/scm/processo_municipio.parquet"
    )
    save_parquet_to_minio(
        ps_ce, "silver/scm/processo_substancia.parquet"
    )
    save_parquet_to_minio(fases_df, "silver/scm/fases.parquet")
    save_parquet_to_minio(tipos_df, "silver/scm/tipos.parquet")


def read_scm_csv(filename: str, columns: list) -> pd.DataFrame:
    """
    Replica o parsing de ScmCsvService.parseCSVFile()
    
    - Delimitador: ;
    - Skip header: sim (primeira linha)
    - Linhas vazias: ignoradas
    - Campos vazios: string vazia
    """
    content = get_from_minio(f"bronze/scm/latest/{filename}")
    
    df = pd.read_csv(
        io.StringIO(content),
        sep=";",
        header=0,           # Primeira linha e cabecalho
        names=columns,
        dtype=str,           # Tudo como string inicialmente
        skip_blank_lines=True,
        encoding="utf-8",
    )
    
    # Tipagem
    int_columns = [
        c for c in columns
        if c.startswith("ID") or c.startswith("NR")
    ]
    for col in int_columns:
        if col in df.columns:
            df[col] = (
                pd.to_numeric(df[col], errors="coerce")
                .fillna(0)
                .astype(int)
            )
    
    return df
```

#### `load_main_tables`

Replica `ScmRepositoryService.bulkInsertProcessos()` com chunks de 500:

```python
def load_main_tables(**context):
    """
    Replica: ScmRepositoryService.bulkInsert*()
    
    Logica original:
    - CLEAR (truncate) cada tabela
    - Remove duplicatas por chave primaria
    - Insere em chunks de 500 registros
    - Em caso de erro no chunk, tenta inserir um a um
      (skip duplicatas)
    
    Chunk size original: 500 (chunkSize = 500)
    """
    
    engine = create_engine(POSTGRES_CONN_STRING)
    
    processos_df = read_parquet_from_minio(
        "silver/scm/processos.parquet"
    )
    pm_df = read_parquet_from_minio(
        "silver/scm/processo_municipio.parquet"
    )
    ps_df = read_parquet_from_minio(
        "silver/scm/processo_substancia.parquet"
    )
    
    CHUNK_SIZE = 500
    
    with engine.begin() as conn:
        conn.execute("TRUNCATE TABLE processos CASCADE")
        
        for i in range(0, len(processos_df), CHUNK_SIZE):
            chunk = processos_df.iloc[i:i + CHUNK_SIZE]
            chunk.to_sql(
                "processos", conn,
                if_exists="append", index=False
            )
        
        conn.execute("TRUNCATE TABLE processo_municipio")
        for i in range(0, len(pm_df), CHUNK_SIZE):
            chunk = pm_df.iloc[i:i + CHUNK_SIZE]
            chunk.to_sql(
                "processo_municipio", conn,
                if_exists="append", index=False
            )
        
        conn.execute("TRUNCATE TABLE processo_substancia")
        for i in range(0, len(ps_df), CHUNK_SIZE):
            chunk = ps_df.iloc[i:i + CHUNK_SIZE]
            chunk.to_sql(
                "processo_substancia", conn,
                if_exists="append", index=False
            )
```

#### `compute_analytics`

Replica as queries analiticas do `ScmRepositoryService`:

```python
def compute_analytics(**context):
    """
    Replica:
    - ScmRepositoryService.getProcessosByFase()
    - ScmRepositoryService.getProcessosByTipo()
    - ScmRepositoryService.getProcessosByMunicipio()
    - ScmRepositoryService.getProcessosBySubstancia()
    - ScmRepositoryService.getProcessosByUF()
    
    Na nova plataforma, estas agregacoes sao materializadas
    como tabelas gold no PostgreSQL.
    """
    
    engine = create_engine(POSTGRES_CONN_STRING)
    
    analytics_queries = {
        "gold_scm_by_fase": """
            SELECT f."DSFaseProcesso" AS fase, COUNT(*) AS count
            FROM processos p
            LEFT JOIN fase_processo f
              ON p."IDFaseProcesso" = f."IDFaseProcesso"
            GROUP BY f."DSFaseProcesso"
            ORDER BY count DESC
        """,
        "gold_scm_by_tipo": """
            SELECT t."DSTipoRequerimento" AS tipo, COUNT(*) AS count
            FROM processos p
            LEFT JOIN tipo_requerimento t
              ON p."IDTipoRequerimento" = t."IDTipoRequerimento"
            GROUP BY t."DSTipoRequerimento"
            ORDER BY count DESC
        """,
        "gold_scm_by_municipio": """
            SELECT m."NMMunicipio" AS municipio, COUNT(*) AS count
            FROM processo_municipio pm
            LEFT JOIN municipio m
              ON pm."IDMunicipio" = m."IDMunicipio"
            GROUP BY m."NMMunicipio"
            ORDER BY count DESC
        """,
        "gold_scm_by_substancia": """
            SELECT s."NMSubstancia" AS substancia, COUNT(*) AS count
            FROM processo_substancia ps
            LEFT JOIN substancia s
              ON ps."IDSubstancia" = s."IDSubstancia"
            GROUP BY s."NMSubstancia"
            ORDER BY count DESC
        """,
        "gold_scm_by_uf": """
            SELECT m."SGUF" AS uf, COUNT(*) AS count
            FROM processo_municipio pm
            LEFT JOIN municipio m
              ON pm."IDMunicipio" = m."IDMunicipio"
            GROUP BY m."SGUF"
            ORDER BY count DESC
        """,
    }
    
    with engine.begin() as conn:
        for table_name, query in analytics_queries.items():
            df = pd.read_sql(query, conn)
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            df.to_sql(
                table_name, conn,
                if_exists="replace", index=False
            )
```

---

## DAG 4: `dag_sigmine_ingestao`

**Substitui:** `SigmineService.getLayer()` e `GeographicFilterService.filterByCearaBounds()`.

**Schedule:** `0 1 * * 0` (semanalmente, domingos as 1h BRT)

**Retry Policy:** 2 tentativas com intervalo de 15 minutos.

**Tags:** `sigmine`, `semanal`, `geo`, `ingestao`

### Tasks

| Task ID | Descricao | Upstream |
|---------|-----------|----------|
| `download_shapefiles` | Baixa ou copia shapefiles das camadas configuradas | - |
| `convert_geojson` | Converte shapefiles para GeoJSON | `download_shapefiles` |
| `filter_ceara` | Aplica filtro de bounding box do Ceara | `convert_geojson` |
| `load_postgresql` | Armazena como JSONB no PostgreSQL (ou PostGIS geometry) | `filter_ceara` |

### Grafo de Dependencias

```
download_shapefiles ──> convert_geojson ──> filter_ceara ──> load_postgresql
```

### Pseudocodigo

#### `download_shapefiles`

```python
def download_shapefiles(**context):
    """
    Replica: A leitura de shapefiles em SigmineService.getLayer()
    
    Layers configuradas (de SIGMINE_LAYER_SHAPEFILES):
    - AREA_SERVIDAO: 'AREA_SERVIDAO/AREA_SERVIDAO.shp'
    - ARRENDAMENTO: 'ARRENDAMENTO/ARRENDAMENTO.shp'
    - BLOQUEIO: 'BLOQUEIO/BLOQUEIO.shp'
    - CE: 'CE/CE.shp'
    - PROTECAO_FONTE: 'PROTECAO_FONTE/PROTECAO_FONTE.shp'
    - RESERVAS_GARIMPEIRAS: 'RESERVAS_GARIMPEIRAS/RESERVAS_GARIMPEIRAS.shp'
    
    Na versao atual, os shapefiles estao em static/ no repositorio.
    Na nova plataforma, eles devem ser armazenados no MinIO bronze.
    """
    
    LAYERS = {
        "area-servidao": "AREA_SERVIDAO/AREA_SERVIDAO.shp",
        "arrendamento": "ARRENDAMENTO/ARRENDAMENTO.shp",
        "bloqueio": "BLOQUEIO/BLOQUEIO.shp",
        "ce": "CE/CE.shp",
        "protecao-fonte": "PROTECAO_FONTE/PROTECAO_FONTE.shp",
        "reservas-garimpeiras":
            "RESERVAS_GARIMPEIRAS/RESERVAS_GARIMPEIRAS.shp",
    }
    
    minio_client = get_minio_client()
    execution_date = context["ds"]
    
    for layer_name, shp_path in LAYERS.items():
        # Copiar shapefile e arquivos associados
        # (.shx, .dbf, .prj) para MinIO
        base_path = shp_path.rsplit(".", 1)[0]
        for ext in [".shp", ".shx", ".dbf", ".prj", ".cpg"]:
            src = f"static/{base_path}{ext}"
            dst = (
                f"bronze/sigmine/"
                f"ano={execution_date[:4]}/"
                f"semana={context['ds_nodash']}/"
                f"{layer_name}{ext}"
            )
            
            minio_client.fput_object("datalake", dst, src)
```

#### `filter_ceara`

Replica `GeographicFilterService.filterByCearaBounds()`:

```python
def filter_ceara(**context):
    """
    Replica: GeographicFilterService.filterByCearaBounds()
    
    LOGICA ORIGINAL:
    1. Carrega geometria do Ceara de 'static/geojs-23-mun.json'
    2. Calcula bounding box do Ceara usando turf.bbox()
    3. Para cada feature do shapefile:
       a. Verifica se geometry.type e 'Polygon' ou 'MultiPolygon'
       b. Calcula bounding box da feature
       c. Verifica overlap entre os dois bounding boxes:
          - feature.east >= ceara.west AND
          - feature.west <= ceara.east AND
          - feature.north >= ceara.south AND
          - feature.south <= ceara.north
    4. Se a layer e 'CE', retorna sem filtrar
       (ja e especifica do Ceara)
    5. Em caso de erro, retorna dados originais (fallback)
    
    BOUNDING BOX DO CEARA (aproximado):
    - Oeste: -41.5
    - Leste: -37.2
    - Sul: -7.9
    - Norte: -2.8
    """
    
    import geopandas as gpd
    from shapely.geometry import box
    
    # Bounding box do Ceara (calculado a partir de geojs-23-mun.json)
    CEARA_BBOX = box(-41.5, -7.9, -37.2, -2.8)
    
    for layer_name in [
        "area-servidao", "arrendamento", "bloqueio",
        "protecao-fonte", "reservas-garimpeiras"
    ]:
        geojson = load_geojson_from_minio(
            f"bronze/sigmine/latest/{layer_name}.geojson"
        )
        
        gdf = gpd.GeoDataFrame.from_features(geojson["features"])
        
        # Filtrar por bounding box (replica a logica de overlap)
        filtered = gdf[gdf.geometry.intersects(CEARA_BBOX)]
        
        # Salvar como GeoJSON no MinIO silver
        save_geojson_to_minio(
            filtered.to_json(),
            f"silver/sigmine/{layer_name}.geojson"
        )
    
    # Layer 'ce' nao precisa de filtro (ja e Ceara)
    ce_geojson = load_geojson_from_minio(
        "bronze/sigmine/latest/ce.geojson"
    )
    save_geojson_to_minio(ce_geojson, "silver/sigmine/ce.geojson")
```

#### `load_postgresql`

```python
def load_postgresql(**context):
    """
    Carrega GeoJSON no PostgreSQL como JSONB.
    
    Alternativa com PostGIS:
    - Usar ST_GeomFromGeoJSON para cada feature
    - Permite queries espaciais nativas
      (ST_Within, ST_Intersects)
    """
    
    engine = create_engine(POSTGRES_CONN_STRING)
    
    LAYERS = [
        "area-servidao", "arrendamento", "bloqueio",
        "ce", "protecao-fonte", "reservas-garimpeiras"
    ]
    
    with engine.begin() as conn:
        conn.execute("TRUNCATE TABLE gold_sigmine_layers")
        
        for layer_name in LAYERS:
            geojson = load_from_minio(
                f"silver/sigmine/{layer_name}.geojson"
            )
            
            conn.execute(
                "INSERT INTO gold_sigmine_layers "
                "(layer_name, geojson_data, updated_at) "
                "VALUES (%s, %s::jsonb, NOW())",
                (layer_name, json.dumps(geojson))
            )
```

---

## Resumo dos Schedules

| DAG | Schedule | Horario (BRT) | Frequencia |
|-----|----------|--------------|------------|
| `dag_scm_ingestao` | `0 2 * * *` | 02:00 | Diaria |
| `dag_comexstat_ingestao` | `0 3 * * *` | 03:00 | Diaria |
| `dag_rde_ingestao` | `0 4 * * *` | 04:00 | Diaria |
| `dag_sigmine_ingestao` | `0 1 * * 0` | 01:00 (dom) | Semanal |

**Nota:** Os horarios foram escalonados para evitar concorrencia entre DAGs e minimizar carga na infraestrutura durante a madrugada. A ordem (SCM as 2h, ComexStat as 3h, RDE as 4h) garante que as DAGs mais rapidas executem primeiro.
