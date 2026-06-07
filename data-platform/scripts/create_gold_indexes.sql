-- =============================================================================
-- create_gold_indexes.sql
-- Índices para as tabelas gold — executar após primeira carga dos pipelines.
-- Melhora queries de API FastAPI de full-scan para index scan.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- ComexStat Summary
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_summary_period_type
    ON gold.gold_comexstat_summary (period_type);

-- ---------------------------------------------------------------------------
-- ComexStat Timeseries
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_timeseries_period
    ON gold.gold_comexstat_timeseries (period_type, year, month);

-- ---------------------------------------------------------------------------
-- ComexStat Partners
-- GET /comexstat/partners?flow=export&period=yearToDate — filtro mais comum
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_partners_lookup
    ON gold.gold_comexstat_partners (period_type, flow, rank);

-- ---------------------------------------------------------------------------
-- ComexStat Products
-- GET /comexstat/products?flow=export&aggregation=heading&period=yearToDate
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_products_lookup
    ON gold.gold_comexstat_products (period_type, flow, aggregation_level, rank);

-- ---------------------------------------------------------------------------
-- ComexStat National Comparison
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_national_comparison_lookup
    ON gold.gold_comexstat_national_comparison (flow, period_type);

-- ---------------------------------------------------------------------------
-- ComexStat States Ranking
-- GET /comexstat/national-comparison/states-ranking?flow=export&from=...&to=...
-- Endpoint mais crítico — índice composto para evitar full scan
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_comexstat_states_ranking_lookup
    ON gold.gold_comexstat_states_ranking (flow, period_type, rank);

-- ---------------------------------------------------------------------------
-- RDE — paginação por Ano/Mes (ORDER BY "Ano" DESC, "Mes" DESC)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_rde_todos_registros_ano_mes
    ON gold.gold_rde_todos_registros ("Ano" DESC, "Mes" DESC);

CREATE INDEX IF NOT EXISTS idx_gold_rde_registros_ied_ano_mes
    ON gold.gold_rde_registros_ied ("Ano" DESC, "Mes" DESC);

CREATE INDEX IF NOT EXISTS idx_gold_rde_registros_ied_cnpj
    ON gold.gold_rde_registros_ied ("CnpjBaseReceptora");

-- ---------------------------------------------------------------------------
-- SCM — busca por numero de processo e filtros analíticos
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_raw_scm_processo_fase
    ON raw.scm_processo (fase_id);

CREATE INDEX IF NOT EXISTS idx_raw_scm_processo_tipo
    ON raw.scm_processo (tipo_id);

CREATE INDEX IF NOT EXISTS idx_raw_scm_processo_municipio_municipio_id
    ON raw.scm_processo_municipio (municipio_id);

CREATE INDEX IF NOT EXISTS idx_raw_scm_processo_substancia_substancia_id
    ON raw.scm_processo_substancia (substancia_id);

-- ---------------------------------------------------------------------------
-- Sigmine/PostGIS — índices espaciais (criados pelo DAG, repetidos aqui para idempotência)
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_gold_sigmine_geometry
    ON gold.gold_sigmine_layers USING GIST (geometry);

CREATE INDEX IF NOT EXISTS idx_gold_sigmine_layer_name
    ON gold.gold_sigmine_layers (layer_name);
