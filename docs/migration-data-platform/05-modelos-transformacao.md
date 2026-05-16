# 05 - Modelos de Transformacao (dbt/Spark)

## Visao Geral

Este documento mapeia **cada metodo de servico** da aplicacao NestJS para um modelo dbt ou job Spark equivalente. O objetivo e garantir que toda a logica de negocio atualmente executada em JavaScript in-memory seja replicada com fidelidade em SQL ou Python.

**Convencao de nomenclatura:**
- Modelos dbt: `gold_<dominio>_<entidade>` (ex: `gold_comexstat_summary`)
- Tabelas staging: `stg_<dominio>_<entidade>` (ex: `stg_comexstat_trade`)
- Funcoes reutilizaveis: macros dbt (ex: `to_millions()`)

---

## Funcoes Utilitarias (Macros dbt)

### `to_millions(value)`

**Metodo NestJS original:** `ComexstatService.toMillions()` em `src/comexstat/comexstat.service.ts` (linha 1038)

**Logica original:**
```javascript
private toMillions(value: unknown): number {
    const numericValue = typeof value === 'string'
        ? Number(value.replace(',', '.'))
        : Number(value);
    if (!Number.isFinite(numericValue)) return 0;
    return numericValue / 1_000_000;
}
```

**Macro dbt:**
```sql
-- macros/to_millions.sql
{% macro to_millions(column) %}
    ROUND(COALESCE({{ column }}::numeric, 0) / 1000000.0, 2)
{% endmacro %}
```

### Resolucao de Periodo

**Metodo NestJS original:** `PeriodStrategyFactory` em `src/comexstat/strategies/period.strategy.ts`

**Logica original:**
- `AnnualPeriodStrategy`: Recebe um ano, retorna `from: YYYY-01`, `to: YYYY-12`. Sem ano, usa `currentYear - 1`.
- `MonthlyPeriodStrategy`: Recebe `PeriodDto {from, to}` ou usa year-to-date. `monthDetail = true`.
- `getCurrentDateInfo()`: Usa data atual menos 2 meses como referencia (delay da API ComexStat).

**Equivalente SQL:**
```sql
-- macros/resolve_period.sql

{% macro current_reference_date() %}
    -- Replica getCurrentDateInfo(): referencia = hoje - 2 meses
    (CURRENT_DATE - INTERVAL '2 months')
{% endmacro %}

{% macro resolve_period(period_type) %}
    {% if period_type == 'currentMonth' %}
        -- previousMonth/previousMonthYear do metodo original
        -- Referencia - 1 mes adicional
        DATE_TRUNC('month', {{ current_reference_date() }} - INTERVAL '1 month')
        AND
        (DATE_TRUNC('month', {{ current_reference_date() }}
            - INTERVAL '1 month')
            + INTERVAL '1 month' - INTERVAL '1 day')
    {% elif period_type == 'yearToDate' %}
        -- from: janeiro do ano da referencia
        -- to: mes da referencia
        DATE_TRUNC('year', {{ current_reference_date() }})
        AND
        (DATE_TRUNC('month', {{ current_reference_date() }})
            + INTERVAL '1 month' - INTERVAL '1 day')
    {% elif period_type == 'lastYear' %}
        -- Ano anterior completo
        DATE_TRUNC('year', {{ current_reference_date() }}
            - INTERVAL '1 year')
        AND
        (DATE_TRUNC('year', {{ current_reference_date() }})
            - INTERVAL '1 day')
    {% endif %}
{% endmacro %}
```

---

## Modelo Staging: `stg_comexstat_trade`

Tabela base que alimenta todos os modelos gold do ComexStat. Materializada na camada silver.

```sql
-- models/staging/stg_comexstat_trade.sql

{{ config(materialized='table') }}

SELECT
    flow,
    year::int                      AS year,
    month_number::int              AS month,
    TO_DATE(
        year || '-' || LPAD(month_number::text, 2, '0') || '-01',
        'YYYY-MM-DD'
    )                              AS period_date,
    year || '-' || LPAD(month_number::text, 2, '0')
                                   AS period_key,
    state_id::int                  AS state_id,
    state_name                     AS state,
    country_name                   AS country,
    isic_section_code              AS isic_section_code,
    isic_section_name              AS isic_section,
    ncm_code                       AS ncm_code,
    ncm_name                       AS ncm,
    heading_code                   AS heading_code,
    heading_name                   AS heading,
    chapter_code                   AS chapter_code,
    chapter_name                   AS chapter,
    metric_fob::numeric            AS metric_fob,
    metric_kg::numeric             AS metric_kg,
    metric_cif::numeric            AS metric_cif
FROM {{ source('silver', 'comexstat_trade_raw') }}
WHERE metric_fob IS NOT NULL
```

---

## Transformacoes ComexStat

### 1. `getSummaryData()` -> `gold_comexstat_summary`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 72)

**Logica de negocio:**
- Filtra por `state_id = 23` (Ceara)
- Agrega `metricFOB` para exportacoes e importacoes no periodo
- Calcula: `tradeBalance = exports - imports`, `tradeCurrent = exports + imports`
- Converte valores para milhoes (`toMillions()`)
- Suporta 4 tipos de periodo: `currentMonth`, `yearToDate`, `lastYear`, `custom`

**Modelo dbt: `gold_comexstat_summary`**

```sql
-- models/gold/comexstat/gold_comexstat_summary.sql

{{ config(materialized='table') }}

WITH period_definitions AS (
    -- Replica os 3 periodos pre-definidos de SummaryPeriod
    SELECT
        'currentMonth' AS period_type,
        DATE_TRUNC('month',
            {{ current_reference_date() }} - INTERVAL '1 month'
        ) AS period_from,
        DATE_TRUNC('month',
            {{ current_reference_date() }}
        ) - INTERVAL '1 day' AS period_to
    UNION ALL
    SELECT
        'yearToDate',
        DATE_TRUNC('year', {{ current_reference_date() }}),
        DATE_TRUNC('month', {{ current_reference_date() }})
            + INTERVAL '1 month' - INTERVAL '1 day'
    UNION ALL
    SELECT
        'lastYear',
        DATE_TRUNC('year',
            {{ current_reference_date() }} - INTERVAL '1 year'
        ),
        DATE_TRUNC('year',
            {{ current_reference_date() }}
        ) - INTERVAL '1 day'
),

exports_by_period AS (
    SELECT
        pd.period_type,
        {{ to_millions('SUM(t.metric_fob)') }} AS exports
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN period_definitions pd
    WHERE t.flow = 'export'
      AND t.state_id = 23  -- CEARA_STATE_ID
      AND t.period_date BETWEEN pd.period_from AND pd.period_to
    GROUP BY pd.period_type
),

imports_by_period AS (
    SELECT
        pd.period_type,
        {{ to_millions('SUM(t.metric_fob)') }} AS imports
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN period_definitions pd
    WHERE t.flow = 'import'
      AND t.state_id = 23
      AND t.period_date BETWEEN pd.period_from AND pd.period_to
    GROUP BY pd.period_type
)

SELECT
    pd.period_type,
    -- Replica formatMonthAbbreviation() para o label do periodo
    CASE pd.period_type
        WHEN 'currentMonth' THEN
            TO_CHAR(pd.period_from, 'Mon')
            || '/' || EXTRACT(YEAR FROM pd.period_from)::text
        WHEN 'yearToDate' THEN
            'Jan-' || TO_CHAR(pd.period_to, 'Mon')
            || '/' || EXTRACT(YEAR FROM pd.period_from)::text
        WHEN 'lastYear' THEN
            EXTRACT(YEAR FROM pd.period_from)::text
    END AS period_label,
    COALESCE(e.exports, 0) AS exports,
    COALESCE(i.imports, 0) AS imports,
    COALESCE(e.exports, 0) - COALESCE(i.imports, 0)
        AS trade_balance,
    COALESCE(e.exports, 0) + COALESCE(i.imports, 0)
        AS trade_current
FROM period_definitions pd
LEFT JOIN exports_by_period e
    ON pd.period_type = e.period_type
LEFT JOIN imports_by_period i
    ON pd.period_type = i.period_type
```

---

### 2. `getSummaryHistory()` -> `gold_comexstat_summary_history`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 161)

**Logica de negocio:**
- Recebe um intervalo `{from: 'YYYY-MM', to: 'YYYY-MM'}`
- Gera lista de todos os meses no intervalo via `generateMonthsRange()`
- Para cada mes: agrega FOB de export e import filtrados por Ceara (`state_id=23`)
- Calcula `tradeBalance` e `tradeCurrent` por mes
- Meses sem dados recebem valores zero (nao sao omitidos)

**Modelo dbt: `gold_comexstat_summary_history`**

```sql
-- models/gold/comexstat/gold_comexstat_summary_history.sql

{{ config(materialized='table') }}

-- Gera serie de todos os meses (replica generateMonthsRange)
-- Na pratica, esta tabela e parametrizada pela API com filtros WHERE

WITH monthly_data AS (
    SELECT
        t.year,
        t.month,
        t.period_key,
        t.flow,
        {{ to_millions('SUM(t.metric_fob)') }} AS value_millions
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23  -- CEARA_STATE_ID
    GROUP BY t.year, t.month, t.period_key, t.flow
),

pivoted AS (
    SELECT
        period_key,
        year,
        month,
        COALESCE(
            MAX(CASE WHEN flow = 'export'
                THEN value_millions END), 0
        ) AS exports,
        COALESCE(
            MAX(CASE WHEN flow = 'import'
                THEN value_millions END), 0
        ) AS imports
    FROM monthly_data
    GROUP BY period_key, year, month
)

SELECT
    period_key,
    year,
    month,
    -- Replica formatMonthAbbreviation(month) + '/' + year
    TO_CHAR(
        TO_DATE(
            year::text || '-'
            || LPAD(month::text, 2, '0')
            || '-01',
            'YYYY-MM-DD'
        ),
        'Mon'
    ) || '/' || year::text AS period_label,
    exports,
    imports,
    exports - imports AS trade_balance,
    exports + imports AS trade_current
FROM pivoted
ORDER BY period_key
```

**Nota sobre filtragem na API:** A FastAPI fara `SELECT * FROM gold_comexstat_summary_history WHERE period_key BETWEEN :from AND :to ORDER BY period_key`. Periodos sem dados serao preenchidos com zeros pela API (ou um LEFT JOIN com `generate_series` pode ser adicionado ao modelo).

---

### 3. `getTimeSeries()` -> `gold_comexstat_timeseries`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 266)

**Logica de negocio:**
- Aceita `periodicity`: `monthly` ou `annual`
- Aceita `series`: `export`, `import`, `current` (soma), `balance` (diferenca)
- Intervalo: `startYear` a `endYear`
- Opcao `includeSectors`: se true, inclui detalhamento por secao ISIC
- Agrega por estado Ceara (`state_id=23`)
- Ordena por periodo (crescente)

**Modelo dbt: `gold_comexstat_timeseries`**

```sql
-- models/gold/comexstat/gold_comexstat_timeseries.sql

{{ config(materialized='table') }}

-- Versao MENSAL (sem setores)
WITH monthly_base AS (
    SELECT
        'monthly' AS periodicity,
        t.period_key AS period,
        t.year::text AS year,
        LPAD(t.month::text, 2, '0') AS month,
        COALESCE(
            SUM(CASE WHEN t.flow = 'export'
                THEN t.metric_fob END), 0
        ) AS raw_exports,
        COALESCE(
            SUM(CASE WHEN t.flow = 'import'
                THEN t.metric_fob END), 0
        ) AS raw_imports
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23
    GROUP BY t.period_key, t.year, t.month
),

-- Versao ANUAL (sem setores)
annual_base AS (
    SELECT
        'annual' AS periodicity,
        t.year::text AS period,
        t.year::text AS year,
        NULL::text AS month,
        COALESCE(
            SUM(CASE WHEN t.flow = 'export'
                THEN t.metric_fob END), 0
        ) AS raw_exports,
        COALESCE(
            SUM(CASE WHEN t.flow = 'import'
                THEN t.metric_fob END), 0
        ) AS raw_imports
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23
    GROUP BY t.year
),

combined AS (
    SELECT * FROM monthly_base
    UNION ALL
    SELECT * FROM annual_base
)

SELECT
    periodicity,
    period,
    year,
    month,
    {{ to_millions('raw_exports') }} AS exports,
    {{ to_millions('raw_imports') }} AS imports,
    -- series = 'current': exports + imports
    {{ to_millions('raw_exports') }}
        + {{ to_millions('raw_imports') }} AS current_value,
    -- series = 'balance': exports - imports
    {{ to_millions('raw_exports') }}
        - {{ to_millions('raw_imports') }} AS balance
FROM combined
ORDER BY periodicity, period
```

**Modelo adicional para setores: `gold_comexstat_timeseries_sectors`**

```sql
-- models/gold/comexstat/gold_comexstat_timeseries_sectors.sql

{{ config(materialized='table') }}

-- Quando includeSectors=true, cada periodo tem lista de setores ISIC

SELECT
    CASE
        WHEN month IS NOT NULL THEN 'monthly'
        ELSE 'annual'
    END AS periodicity,
    CASE
        WHEN month IS NOT NULL
        THEN year::text || '-' || LPAD(month::text, 2, '0')
        ELSE year::text
    END AS period,
    t.year::text AS year,
    CASE
        WHEN month IS NOT NULL
        THEN LPAD(month::text, 2, '0')
    END AS month,
    t.flow,
    t.isic_section_code AS sector_code,
    t.isic_section AS sector_name,
    {{ to_millions('SUM(t.metric_fob)') }} AS sector_value
FROM {{ ref('stg_comexstat_trade') }} t
WHERE t.state_id = 23
  AND t.isic_section IS NOT NULL
GROUP BY
    t.year, t.month, t.flow,
    t.isic_section_code, t.isic_section
ORDER BY period, sector_value DESC
```

---

### 4. `getPartnerCountries()` -> `gold_comexstat_partners`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 409)

**Logica de negocio:**
- Filtra por Ceara (`state_id=23`)
- Agrupa por pais, acumula `metricFOB` por fluxo
- Calcula `current = exports + imports`, `balance = exports - imports`
- Calcula `percentage = base / total * 100` (base depende do fluxo)
- Ordena pelo valor do fluxo selecionado (descendente)
- Retorna top N (padrao 10)

**Modelo dbt: `gold_comexstat_partners`**

```sql
-- models/gold/comexstat/gold_comexstat_partners.sql

{{ config(materialized='table') }}

WITH partner_values AS (
    SELECT
        pd.period_type,
        t.country,
        {{ to_millions(
            "SUM(CASE WHEN t.flow = 'export'"
            " THEN t.metric_fob ELSE 0 END)"
        ) }} AS exports,
        {{ to_millions(
            "SUM(CASE WHEN t.flow = 'import'"
            " THEN t.metric_fob ELSE 0 END)"
        ) }} AS imports
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
            ),
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'
            ),
            DATE_TRUNC('year',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day'
    ) pd
    WHERE t.state_id = 23
      AND t.period_date
          BETWEEN pd.period_from AND pd.period_to
      AND t.country IS NOT NULL
    GROUP BY pd.period_type, t.country
),

with_derived AS (
    SELECT
        period_type,
        country,
        exports,
        imports,
        exports + imports AS current_value,
        exports - imports AS balance,
        -- Percentual por fluxo (export)
        CASE
            WHEN SUM(exports)
                OVER (PARTITION BY period_type) > 0
            THEN exports
                / SUM(exports)
                    OVER (PARTITION BY period_type)
                * 100
            ELSE 0
        END AS pct_export,
        -- Percentual por fluxo (import)
        CASE
            WHEN SUM(imports)
                OVER (PARTITION BY period_type) > 0
            THEN imports
                / SUM(imports)
                    OVER (PARTITION BY period_type)
                * 100
            ELSE 0
        END AS pct_import,
        -- Percentual por corrente
        CASE
            WHEN SUM(exports + imports)
                OVER (PARTITION BY period_type) > 0
            THEN (exports + imports)
                / SUM(exports + imports)
                    OVER (PARTITION BY period_type)
                * 100
            ELSE 0
        END AS pct_current,
        -- Ranking por fluxo
        ROW_NUMBER() OVER (
            PARTITION BY period_type
            ORDER BY exports DESC
        ) AS rank_export,
        ROW_NUMBER() OVER (
            PARTITION BY period_type
            ORDER BY imports DESC
        ) AS rank_import,
        ROW_NUMBER() OVER (
            PARTITION BY period_type
            ORDER BY (exports + imports) DESC
        ) AS rank_current
    FROM partner_values
)

SELECT * FROM with_derived
```

**Consulta da FastAPI:**
```sql
-- Para flow=export, period=yearToDate, topN=10
SELECT
    country, exports, imports,
    current_value, balance,
    pct_export AS percentage
FROM gold_comexstat_partners
WHERE period_type = 'yearToDate'
ORDER BY rank_export
LIMIT 10
```

---

### 5. `getTopProducts()` -> `gold_comexstat_products`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 562)

**Logica de negocio:**
- Aceita `flow`: `export` ou `import`
- Aceita `periodicity`: `monthly` (com `PeriodDto`) ou `annual` (com ano)
- Aceita `aggregation`: `ncm` (8 digitos), `heading` (4 digitos), `chapter` (2 digitos)
- Mapeamento de campos (do `fieldMap` no metodo original):
  - `ncm` -> `{code: 'ncmCode', desc: 'ncm'}`
  - `heading` -> `{code: 'headingCode', desc: 'heading'}`
  - `chapter` -> `{code: 'chapterCode', desc: 'chapter'}`
- Calcula `percentage = value / totalValue * 100`
- Inclui `weight` (`metricKG`) quando disponivel
- Ordena por valor (descendente), retorna top N (padrao 20)

**Modelo dbt: `gold_comexstat_products`**

```sql
-- models/gold/comexstat/gold_comexstat_products.sql

{{ config(materialized='table') }}

-- HEADING (4 digitos) - nivel de agregacao padrao
WITH heading_products AS (
    SELECT
        t.flow,
        'heading' AS aggregation,
        t.year,
        t.heading_code AS code,
        t.heading AS description,
        {{ to_millions('SUM(t.metric_fob)') }} AS value,
        SUM(t.metric_kg) AS weight
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23
      AND t.heading_code IS NOT NULL
    GROUP BY
        t.flow, t.year,
        t.heading_code, t.heading
),

-- NCM (8 digitos)
ncm_products AS (
    SELECT
        t.flow,
        'ncm' AS aggregation,
        t.year,
        t.ncm_code AS code,
        t.ncm AS description,
        {{ to_millions('SUM(t.metric_fob)') }} AS value,
        SUM(t.metric_kg) AS weight
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23
      AND t.ncm_code IS NOT NULL
    GROUP BY
        t.flow, t.year,
        t.ncm_code, t.ncm
),

-- CHAPTER (2 digitos)
chapter_products AS (
    SELECT
        t.flow,
        'chapter' AS aggregation,
        t.year,
        t.chapter_code AS code,
        t.chapter AS description,
        {{ to_millions('SUM(t.metric_fob)') }} AS value,
        SUM(t.metric_kg) AS weight
    FROM {{ ref('stg_comexstat_trade') }} t
    WHERE t.state_id = 23
      AND t.chapter_code IS NOT NULL
    GROUP BY
        t.flow, t.year,
        t.chapter_code, t.chapter
),

all_products AS (
    SELECT * FROM heading_products
    UNION ALL
    SELECT * FROM ncm_products
    UNION ALL
    SELECT * FROM chapter_products
),

with_pct AS (
    SELECT
        *,
        -- Replica: percentage = totalValue > 0
        --   ? (product.value / totalValue) * 100 : 0
        CASE
            WHEN SUM(value) OVER (
                PARTITION BY flow, aggregation, year
            ) > 0
            THEN value / SUM(value) OVER (
                PARTITION BY flow, aggregation, year
            ) * 100
            ELSE 0
        END AS percentage,
        ROW_NUMBER() OVER (
            PARTITION BY flow, aggregation, year
            ORDER BY value DESC
        ) AS rank
    FROM all_products
)

SELECT
    flow,
    aggregation,
    year,
    code,
    description,
    value,
    weight,
    percentage,
    rank
FROM with_pct
```

**Consulta da FastAPI:**
```sql
-- Para flow=export, aggregation=heading, year=2025, topN=20
SELECT code, description, value, weight, percentage
FROM gold_comexstat_products
WHERE flow = 'export'
  AND aggregation = 'heading'
  AND year = 2025
ORDER BY rank
LIMIT 20
```

---

### 6. `getNationalComparison()` -> `gold_comexstat_national_comparison`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 641)

**Logica de negocio:**
- Faz 3 queries paralelas:
  1. Total nacional (sem filtro de estado)
  2. Total do Ceara (`state_id=23`)
  3. Todos os estados (com detalhamento por estado)
- Calcula `participation = cearaTotal / nationalTotal * 100`
- Calcula ranking do Ceara entre os 27 estados (1-indexed)

**Modelo dbt: `gold_comexstat_national_comparison`**

```sql
-- models/gold/comexstat/gold_comexstat_national_comparison.sql

{{ config(materialized='table') }}

WITH state_totals AS (
    SELECT
        pd.period_type,
        t.flow,
        t.state,
        t.state_id,
        SUM(t.metric_fob) AS total_fob
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}),
            DATE_TRUNC('month',
                {{ current_reference_date() }})
                + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'),
            DATE_TRUNC('year',
                {{ current_reference_date() }})
                - INTERVAL '1 day'
    ) pd
    WHERE t.period_date
        BETWEEN pd.period_from AND pd.period_to
    GROUP BY
        pd.period_type, t.flow, t.state, t.state_id
),

national_totals AS (
    SELECT
        period_type,
        flow,
        SUM(total_fob) AS national_total
    FROM state_totals
    GROUP BY period_type, flow
),

ranked_states AS (
    SELECT
        st.period_type,
        st.flow,
        st.state,
        st.state_id,
        st.total_fob,
        nt.national_total,
        -- Replica:
        --   ranking = states.findIndex(
        --     s => s.state === 'Ceara'
        --   ) + 1
        RANK() OVER (
            PARTITION BY st.period_type, st.flow
            ORDER BY st.total_fob DESC
        ) AS ranking,
        -- Replica:
        --   participation = nationalTotal > 0
        --     ? (cearaTotal / nationalTotal) * 100
        --     : 0
        CASE
            WHEN nt.national_total > 0
            THEN (st.total_fob / nt.national_total) * 100
            ELSE 0
        END AS participation
    FROM state_totals st
    JOIN national_totals nt
        ON st.period_type = nt.period_type
        AND st.flow = nt.flow
)

SELECT
    period_type,
    flow,
    participation,
    ranking::int
FROM ranked_states
WHERE state_id = 23  -- Ceara
```

**Consulta da FastAPI:**
```sql
SELECT participation, ranking
FROM gold_comexstat_national_comparison
WHERE flow = 'export'
  AND period_type = 'yearToDate'
```

---

### 7. `getStatesRanking()` -> `gold_comexstat_states_ranking`

**Arquivo NestJS:** `src/comexstat/comexstat.service.ts` (linha 697)

**Esta e a operacao MAIS CARA do sistema atual.** O metodo faz 5 chamadas paralelas a API ComexStat:
1. Total nacional
2. Valores por estado
3. Setores por estado (state + ISICSection)
4. Parceiros por estado (state + country)
5. Produtos por estado (state + heading)

E depois agrega tudo em JavaScript com Maps para montar o ranking de 27 estados, cada um com top 5 setores, top 5 parceiros e top 5 produtos.

**Modelos dbt:**

#### 7a. `gold_comexstat_states_ranking_base` - Ranking base dos estados

```sql
-- models/gold/comexstat/gold_comexstat_states_ranking_base.sql

{{ config(materialized='table') }}

WITH state_values AS (
    SELECT
        pd.period_type,
        t.flow,
        t.state,
        {{ to_millions('SUM(t.metric_fob)') }} AS value,
        SUM(t.metric_fob) AS raw_value
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}),
            DATE_TRUNC('month',
                {{ current_reference_date() }})
                + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'),
            DATE_TRUNC('year',
                {{ current_reference_date() }})
                - INTERVAL '1 day'
    ) pd
    WHERE t.period_date
        BETWEEN pd.period_from AND pd.period_to
    GROUP BY pd.period_type, t.flow, t.state
),

national_total AS (
    SELECT
        period_type,
        flow,
        SUM(raw_value) AS total
    FROM state_values
    GROUP BY period_type, flow
)

SELECT
    sv.period_type,
    sv.flow,
    -- Replica:
    --   .sort((a, b) => b.rawValue - a.rawValue)
    --   .map((item, index) => ({ rank: index + 1 }))
    ROW_NUMBER() OVER (
        PARTITION BY sv.period_type, sv.flow
        ORDER BY sv.raw_value DESC
    )::int AS rank,
    sv.state,
    sv.value,
    -- Replica:
    --   participation = nationalTotal > 0
    --     ? (item.rawValue / nationalTotal) * 100
    --     : 0
    CASE
        WHEN nt.total > 0
        THEN (sv.raw_value / nt.total) * 100
        ELSE 0
    END AS participation
FROM state_values sv
JOIN national_total nt
    ON sv.period_type = nt.period_type
    AND sv.flow = nt.flow
ORDER BY sv.period_type, sv.flow, rank
```

#### 7b. `gold_comexstat_states_top_sectors` - Top 5 setores por estado

```sql
-- models/gold/comexstat/gold_comexstat_states_top_sectors.sql

{{ config(materialized='table') }}

WITH sector_values AS (
    SELECT
        pd.period_type,
        t.flow,
        t.state,
        t.isic_section_code AS code,
        t.isic_section AS name,
        {{ to_millions('SUM(t.metric_fob)') }} AS value
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}),
            DATE_TRUNC('month',
                {{ current_reference_date() }})
                + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'),
            DATE_TRUNC('year',
                {{ current_reference_date() }})
                - INTERVAL '1 day'
    ) pd
    WHERE t.period_date
        BETWEEN pd.period_from AND pd.period_to
      AND t.isic_section IS NOT NULL
    GROUP BY
        pd.period_type, t.flow, t.state,
        t.isic_section_code, t.isic_section
),

ranked AS (
    SELECT
        *,
        -- Total do estado para calculo de percentual
        SUM(value) OVER (
            PARTITION BY period_type, flow, state
        ) AS state_total,
        -- Replica:
        --   sectors.sort((a,b) => b.value-a.value)
        --   .slice(0, 5)
        ROW_NUMBER() OVER (
            PARTITION BY period_type, flow, state
            ORDER BY value DESC
        ) AS rank_in_state
    FROM sector_values
)

SELECT
    period_type,
    flow,
    state,
    code,
    name,
    value,
    -- Replica:
    --   percentage = sectorTotal > 0
    --     ? (s.value / sectorTotal) * 100
    --     : 0
    CASE
        WHEN state_total > 0
        THEN (value / state_total) * 100
        ELSE 0
    END AS percentage,
    rank_in_state
FROM ranked
WHERE rank_in_state <= 5
```

#### 7c. `gold_comexstat_states_top_partners` - Top 5 parceiros por estado

```sql
-- models/gold/comexstat/gold_comexstat_states_top_partners.sql

{{ config(materialized='table') }}

WITH partner_values AS (
    SELECT
        pd.period_type,
        t.flow,
        t.state,
        t.country,
        {{ to_millions('SUM(t.metric_fob)') }} AS value
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}),
            DATE_TRUNC('month',
                {{ current_reference_date() }})
                + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'),
            DATE_TRUNC('year',
                {{ current_reference_date() }})
                - INTERVAL '1 day'
    ) pd
    WHERE t.period_date
        BETWEEN pd.period_from AND pd.period_to
      AND t.country IS NOT NULL
    GROUP BY
        pd.period_type, t.flow, t.state, t.country
),

ranked AS (
    SELECT
        *,
        SUM(value) OVER (
            PARTITION BY period_type, flow, state
        ) AS state_total,
        -- Replica:
        --   partners.sort((a,b) => b.value-a.value)
        --   .slice(0, 5)
        ROW_NUMBER() OVER (
            PARTITION BY period_type, flow, state
            ORDER BY value DESC
        ) AS rank_in_state
    FROM partner_values
)

SELECT
    period_type,
    flow,
    state,
    country,
    value,
    -- Replica:
    --   percentage = partnerTotal > 0
    --     ? (p.value / partnerTotal) * 100
    --     : 0
    CASE
        WHEN state_total > 0
        THEN (value / state_total) * 100
        ELSE 0
    END AS percentage,
    rank_in_state
FROM ranked
WHERE rank_in_state <= 5
```

#### 7d. `gold_comexstat_states_top_products` - Top 5 produtos por estado

```sql
-- models/gold/comexstat/gold_comexstat_states_top_products.sql

{{ config(materialized='table') }}

-- Nota: O metodo original usa 'heading' (4 digitos)
-- para products no states ranking.
-- Vide: details: ['state', 'heading'] na chamada queryGeneral()

WITH product_values AS (
    SELECT
        pd.period_type,
        t.flow,
        t.state,
        t.heading_code AS code,
        t.heading AS description,
        {{ to_millions('SUM(t.metric_fob)') }} AS value
    FROM {{ ref('stg_comexstat_trade') }} t
    CROSS JOIN (
        SELECT 'currentMonth' AS period_type,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
                - INTERVAL '1 month'
            ) AS period_from,
            DATE_TRUNC('month',
                {{ current_reference_date() }}
            ) - INTERVAL '1 day' AS period_to
        UNION ALL
        SELECT 'yearToDate',
            DATE_TRUNC('year',
                {{ current_reference_date() }}),
            DATE_TRUNC('month',
                {{ current_reference_date() }})
                + INTERVAL '1 month' - INTERVAL '1 day'
        UNION ALL
        SELECT 'lastYear',
            DATE_TRUNC('year',
                {{ current_reference_date() }}
                - INTERVAL '1 year'),
            DATE_TRUNC('year',
                {{ current_reference_date() }})
                - INTERVAL '1 day'
    ) pd
    WHERE t.period_date
        BETWEEN pd.period_from AND pd.period_to
      AND t.heading_code IS NOT NULL
    GROUP BY
        pd.period_type, t.flow, t.state,
        t.heading_code, t.heading
),

ranked AS (
    SELECT
        *,
        SUM(value) OVER (
            PARTITION BY period_type, flow, state
        ) AS state_total,
        ROW_NUMBER() OVER (
            PARTITION BY period_type, flow, state
            ORDER BY value DESC
        ) AS rank_in_state
    FROM product_values
)

SELECT
    period_type,
    flow,
    state,
    code,
    description,
    value,
    CASE
        WHEN state_total > 0
        THEN (value / state_total) * 100
        ELSE 0
    END AS percentage,
    rank_in_state
FROM ranked
WHERE rank_in_state <= 5
```

**Consulta da FastAPI para montar a resposta completa do states ranking:**
```sql
-- A API precisa combinar os 4 modelos
-- para montar o StateRankingItemDto

-- 1. Buscar ranking base
SELECT rank, state, value, participation
FROM gold_comexstat_states_ranking_base
WHERE flow = :flow AND period_type = :period_type
ORDER BY rank;

-- 2. Para cada estado, buscar top 5 setores
SELECT state, code, name, value, percentage
FROM gold_comexstat_states_top_sectors
WHERE flow = :flow
  AND period_type = :period_type
  AND rank_in_state <= 5
ORDER BY state, rank_in_state;

-- 3. Para cada estado, buscar top 5 parceiros
SELECT state, country, value, percentage
FROM gold_comexstat_states_top_partners
WHERE flow = :flow
  AND period_type = :period_type
  AND rank_in_state <= 5
ORDER BY state, rank_in_state;

-- 4. Para cada estado, buscar top 5 produtos
SELECT state, code, description, value, percentage
FROM gold_comexstat_states_top_products
WHERE flow = :flow
  AND period_type = :period_type
  AND rank_in_state <= 5
ORDER BY state, rank_in_state;
```

---

### 8. `getDashboard()` -> `gold_comexstat_dashboard`

**Arquivo NestJS:** O dashboard combina dados de `getSummaryData()`, `getTopProducts()` e `getPartnerCountries()`.

**Logica de negocio (inferida do `DashboardDataDto`):**
- `summary`: Resumo year-to-date (ou ano especifico)
- `topExports`: Top 10 produtos exportados (heading, annual)
- `topImports`: Top 10 produtos importados (heading, annual)
- `topPartners`: Top 10 parceiros comerciais (corrente, year-to-date)

**Modelo dbt: `gold_comexstat_dashboard`**

Este modelo nao precisa de SQL proprio - a FastAPI combina os modelos existentes:

```sql
-- Na FastAPI, o endpoint /dashboard executa:

-- summary (reutiliza gold_comexstat_summary)
SELECT *
FROM gold_comexstat_summary
WHERE period_type = CASE
    WHEN :year IS NOT NULL THEN 'lastYear'
    ELSE 'yearToDate'
END;

-- topExports (reutiliza gold_comexstat_products)
SELECT code, description, value, weight, percentage
FROM gold_comexstat_products
WHERE flow = 'export'
  AND aggregation = 'heading'
  AND year = COALESCE(
      :year,
      EXTRACT(YEAR FROM CURRENT_DATE)::int
  )
ORDER BY rank
LIMIT 10;

-- topImports
SELECT code, description, value, weight, percentage
FROM gold_comexstat_products
WHERE flow = 'import'
  AND aggregation = 'heading'
  AND year = COALESCE(
      :year,
      EXTRACT(YEAR FROM CURRENT_DATE)::int
  )
ORDER BY rank
LIMIT 10;

-- topPartners (reutiliza gold_comexstat_partners)
SELECT
    country, exports, imports,
    current_value, balance,
    pct_current AS percentage
FROM gold_comexstat_partners
WHERE period_type = 'yearToDate'
ORDER BY rank_current
LIMIT 10;
```

---

## Transformacoes SCM

### `getProcessosByFase()` -> `gold_scm_by_fase`

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 206)

**Logica original:**
```javascript
.leftJoin(FaseProcesso, 'f',
    'p.IDFaseProcesso = f.IDFaseProcesso')
.select('f.DSFaseProcesso', 'fase')
.addSelect('COUNT(*)', 'count')
.groupBy('f.DSFaseProcesso')
```

**Modelo dbt:**
```sql
-- models/gold/scm/gold_scm_by_fase.sql
{{ config(materialized='table') }}

SELECT
    COALESCE(f."DSFaseProcesso", 'Desconhecido') AS fase,
    COUNT(*)::int AS count
FROM {{ ref('stg_scm_processos') }} p
LEFT JOIN {{ ref('stg_scm_fases') }} f
    ON p."IDFaseProcesso" = f."IDFaseProcesso"
GROUP BY f."DSFaseProcesso"
ORDER BY count DESC
```

### `getProcessosByTipo()` -> `gold_scm_by_tipo`

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 221)

```sql
-- models/gold/scm/gold_scm_by_tipo.sql
{{ config(materialized='table') }}

SELECT
    COALESCE(
        t."DSTipoRequerimento", 'Desconhecido'
    ) AS tipo,
    COUNT(*)::int AS count
FROM {{ ref('stg_scm_processos') }} p
LEFT JOIN {{ ref('stg_scm_tipos') }} t
    ON p."IDTipoRequerimento" = t."IDTipoRequerimento"
GROUP BY t."DSTipoRequerimento"
ORDER BY count DESC
```

### `getProcessosByMunicipio()` -> `gold_scm_by_municipio`

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 236)

```sql
-- models/gold/scm/gold_scm_by_municipio.sql
{{ config(materialized='table') }}

SELECT
    COALESCE(m."NMMunicipio", 'Desconhecido') AS municipio,
    COUNT(*)::int AS count
FROM {{ ref('stg_scm_processo_municipio') }} pm
LEFT JOIN {{ ref('stg_scm_municipios') }} m
    ON pm."IDMunicipio" = m."IDMunicipio"
GROUP BY m."NMMunicipio"
ORDER BY count DESC
```

### `getProcessosBySubstancia()` -> `gold_scm_by_substancia`

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 251)

```sql
-- models/gold/scm/gold_scm_by_substancia.sql
{{ config(materialized='table') }}

SELECT
    COALESCE(
        s."NMSubstancia", 'Desconhecido'
    ) AS substancia,
    COUNT(*)::int AS count
FROM {{ ref('stg_scm_processo_substancia') }} ps
LEFT JOIN {{ ref('stg_scm_substancias') }} s
    ON ps."IDSubstancia" = s."IDSubstancia"
GROUP BY s."NMSubstancia"
ORDER BY count DESC
```

### `getProcessosByUF()` -> `gold_scm_by_uf`

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 266)

```sql
-- models/gold/scm/gold_scm_by_uf.sql
{{ config(materialized='table') }}

-- Nota: com a filtragem para Ceara na ingestao,
-- esta tabela tera predominantemente (ou exclusivamente)
-- registros de 'CE'.
-- Mantida para compatibilidade com a API atual.

SELECT
    COALESCE(m."SGUF", 'Desconhecido') AS uf,
    COUNT(*)::int AS count
FROM {{ ref('stg_scm_processo_municipio') }} pm
LEFT JOIN {{ ref('stg_scm_municipios') }} m
    ON pm."IDMunicipio" = m."IDMunicipio"
GROUP BY m."SGUF"
ORDER BY count DESC
```

### `findProcessosByFilters()` -> View parametrizada

**Arquivo NestJS:** `src/scm/scm-repository.service.ts` (linha 327)

**Logica original:** Query builder com filtros dinamicos (processo, municipio, substancia, fase, tipo, limit).

**Na nova plataforma:** Nao e um modelo dbt materializado. A FastAPI consulta diretamente as tabelas staging com filtros SQL:

```sql
-- FastAPI - endpoint de busca de processos
SELECT p.*
FROM stg_scm_processos p
WHERE 1=1
  AND (:processo IS NULL
      OR p."DSProcesso" = :processo)
  AND (:fase IS NULL
      OR p."IDFaseProcesso" = :fase)
  AND (:tipo IS NULL
      OR p."IDTipoRequerimento" = :tipo)
  AND (:municipio IS NULL OR EXISTS (
      SELECT 1
      FROM stg_scm_processo_municipio pm
      WHERE pm."DSProcesso" = p."DSProcesso"
        AND pm."IDMunicipio" = :municipio
  ))
  AND (:substancia IS NULL OR EXISTS (
      SELECT 1
      FROM stg_scm_processo_substancia ps
      WHERE ps."DSProcesso" = p."DSProcesso"
        AND ps."IDSubstancia" = :substancia
  ))
LIMIT COALESCE(:limit, 100)
```

---

## Transformacoes RDE

### `getTodosRegistros()` -> `gold_rde_todos_registros`

**Arquivo NestJS:** `src/rde/rde.service.ts` (linha 34)

**Logica de negocio:** Essencialmente pass-through. O filtro principal (`contains(UfPessoaNacional,'CE')`) e aplicado na ingestao. A API apenas expoe com paginacao e ordenacao.

```sql
-- models/gold/rde/gold_rde_todos_registros.sql
{{ config(materialized='table') }}

-- Filtro de Ceara ja aplicado na ingestao
-- (buildODataParams: $filter=contains(UfPessoaNacional,'CE'))
SELECT
    "CodigoRDE",
    "NomePessoaNacional",
    "UfPessoaNacional",
    "NomePessoaEstrangeira",
    "PaisPessoaEstrangeira",
    "MoedaOperacao",
    "ValorOperacao"::numeric AS "ValorOperacao",
    "Sistema",
    "Ocorrencia",
    "Modalidade",
    "Ano"::int AS "Ano",
    "Mes"::int AS "Mes"
FROM {{ ref('stg_rde_todos_registros') }}
ORDER BY "Ano" DESC, "Mes" DESC
```

### `getRegistrosIed()` -> `gold_rde_registros_ied`

**Arquivo NestJS:** `src/rde/rde.service.ts` (linha 65)

```sql
-- models/gold/rde/gold_rde_registros_ied.sql
{{ config(materialized='table') }}

SELECT
    "CodigoRDE",
    "CnpjBaseReceptora",
    "NomePessoaNacional",
    "UfPessoaNacional",
    "NomePessoaEstrangeira",
    "PaisPessoaEstrangeira",
    "MoedaOperacao",
    "ValorOperacao"::numeric AS "ValorOperacao",
    "Sistema",
    "Ocorrencia",
    "Modalidade",
    "Ano"::int AS "Ano",
    "Mes"::int AS "Mes"
FROM {{ ref('stg_rde_registros_ied') }}
ORDER BY "Ano" DESC, "Mes" DESC
```

**Consulta da FastAPI com paginacao (replica buildODataParams):**
```sql
SELECT *
FROM gold_rde_todos_registros
ORDER BY
    "Ano" DESC,   -- orderAno padrao 'desc'
    "Mes" DESC    -- orderMes padrao 'desc'
OFFSET :skip
LIMIT :top        -- padrao 100
```

---

## Transformacoes SIGMINE

### `getLayer()` -> `gold_sigmine_layers`

**Arquivo NestJS:** `src/sigmine/sigmine.service.ts` (linha 30)

**Logica de negocio:**
- Le shapefile de `static/`
- Converte para GeoJSON via biblioteca `shapefile`
- Se a camada nao e `CE`, aplica filtro geografico (`filterByCearaBounds`)
- Cache de 24h

**Na nova plataforma:** Nao e um modelo dbt (dados geoespaciais). Os dados sao processados pelo Spark/Python na DAG e armazenados como JSONB no PostgreSQL.

```sql
-- DDL da tabela gold (nao e dbt, e criada pela migracao)
CREATE TABLE gold_sigmine_layers (
    layer_name VARCHAR(50) PRIMARY KEY,
    geojson_data JSONB NOT NULL,
    feature_count INT,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Opcional: com PostGIS para queries espaciais
CREATE TABLE gold_sigmine_features (
    id SERIAL PRIMARY KEY,
    layer_name VARCHAR(50) NOT NULL,
    properties JSONB,
    geom GEOMETRY(Geometry, 4326),
    CONSTRAINT fk_layer FOREIGN KEY (layer_name)
        REFERENCES gold_sigmine_layers(layer_name)
);

CREATE INDEX idx_sigmine_geom
    ON gold_sigmine_features USING GIST (geom);
```

**Consulta da FastAPI:**
```sql
-- Endpoint GET /sigmine/:layer
SELECT geojson_data
FROM gold_sigmine_layers
WHERE layer_name = :layer
```

---

## Resumo do Mapeamento Completo

| Metodo NestJS | Arquivo | Modelo dbt/Tabela Gold | Tipo |
|---------------|---------|------------------------|------|
| `getSummaryData()` | `comexstat.service.ts:72` | `gold_comexstat_summary` | dbt model |
| `getSummaryHistory()` | `comexstat.service.ts:161` | `gold_comexstat_summary_history` | dbt model |
| `getTimeSeries()` | `comexstat.service.ts:266` | `gold_comexstat_timeseries` | dbt model |
| `getTimeSeries(sectors)` | `comexstat.service.ts:266` | `gold_comexstat_timeseries_sectors` | dbt model |
| `getPartnerCountries()` | `comexstat.service.ts:409` | `gold_comexstat_partners` | dbt model |
| `getTopProducts()` | `comexstat.service.ts:562` | `gold_comexstat_products` | dbt model |
| `getNationalComparison()` | `comexstat.service.ts:641` | `gold_comexstat_national_comparison` | dbt model |
| `getStatesRanking()` | `comexstat.service.ts:697` | `gold_comexstat_states_ranking_base` | dbt model |
| `getStatesRanking()` (setores) | `comexstat.service.ts:697` | `gold_comexstat_states_top_sectors` | dbt model |
| `getStatesRanking()` (parceiros) | `comexstat.service.ts:697` | `gold_comexstat_states_top_partners` | dbt model |
| `getStatesRanking()` (produtos) | `comexstat.service.ts:697` | `gold_comexstat_states_top_products` | dbt model |
| `getDashboard()` | controller | Combina summary + products + partners | Consulta FastAPI |
| `getProcessosByFase()` | `scm-repository.service.ts:206` | `gold_scm_by_fase` | dbt model |
| `getProcessosByTipo()` | `scm-repository.service.ts:221` | `gold_scm_by_tipo` | dbt model |
| `getProcessosByMunicipio()` | `scm-repository.service.ts:236` | `gold_scm_by_municipio` | dbt model |
| `getProcessosBySubstancia()` | `scm-repository.service.ts:251` | `gold_scm_by_substancia` | dbt model |
| `getProcessosByUF()` | `scm-repository.service.ts:266` | `gold_scm_by_uf` | dbt model |
| `findProcessosByFilters()` | `scm-repository.service.ts:327` | Query parametrizada na FastAPI | Consulta direta |
| `getTodosRegistros()` | `rde.service.ts:34` | `gold_rde_todos_registros` | dbt model |
| `getRegistrosIed()` | `rde.service.ts:65` | `gold_rde_registros_ied` | dbt model |
| `getLayer()` | `sigmine.service.ts:30` | `gold_sigmine_layers` | Tabela PostgreSQL |
| `filterByCearaBounds()` | `geographic-filter.service.ts:44` | Logica no Spark/Python (DAG) | Job Python |
| `filterDataForCeara()` | `scm-csv.service.ts:462` | Logica no Pandas (DAG) | Job Python |
| `toMillions()` | `comexstat.service.ts:1038` | Macro dbt `to_millions()` | Macro SQL |
| `PeriodStrategyFactory` | `strategies/period.strategy.ts` | Macro dbt `resolve_period()` | Macro SQL |

---

## Grafo de Dependencias dbt

```
stg_comexstat_trade
    |
    +---> gold_comexstat_summary
    +---> gold_comexstat_summary_history
    +---> gold_comexstat_timeseries
    +---> gold_comexstat_timeseries_sectors
    +---> gold_comexstat_partners
    +---> gold_comexstat_products
    +---> gold_comexstat_national_comparison
    +---> gold_comexstat_states_ranking_base
    +---> gold_comexstat_states_top_sectors
    +---> gold_comexstat_states_top_partners
    +---> gold_comexstat_states_top_products

stg_scm_processos + stg_scm_fases + stg_scm_tipos
    +---> gold_scm_by_fase
    +---> gold_scm_by_tipo

stg_scm_processo_municipio + stg_scm_municipios
    +---> gold_scm_by_municipio
    +---> gold_scm_by_uf

stg_scm_processo_substancia + stg_scm_substancias
    +---> gold_scm_by_substancia

stg_rde_todos_registros
    +---> gold_rde_todos_registros

stg_rde_registros_ied
    +---> gold_rde_registros_ied
```

---

## Testes dbt Recomendados

```yaml
# models/gold/comexstat/schema.yml

version: 2

models:
  - name: gold_comexstat_summary
    description: >
      Resumo do comercio exterior do Ceara
      por tipo de periodo
    columns:
      - name: period_type
        tests:
          - not_null
          - accepted_values:
              values:
                - 'currentMonth'
                - 'yearToDate'
                - 'lastYear'
      - name: exports
        tests:
          - not_null
      - name: trade_balance
        description: "exports - imports"

  - name: gold_comexstat_states_ranking_base
    description: "Ranking de estados por valor FOB"
    columns:
      - name: rank
        tests:
          - not_null
          - unique:
              config:
                where: >
                  period_type = 'yearToDate'
                  AND flow = 'export'
      - name: participation
        description: >
          Percentual do estado no total nacional
        tests:
          - not_null

  - name: gold_scm_by_fase
    description: >
      Contagem de processos minerarios por fase
    columns:
      - name: fase
        tests:
          - not_null
          - unique
      - name: count
        tests:
          - not_null
```
