-- Airflow database
CREATE USER airflow WITH PASSWORD 'airflow';
CREATE DATABASE airflow OWNER airflow;

-- Warehouse database (read by NestJS API)
CREATE USER warehouse WITH PASSWORD 'warehouse';
CREATE DATABASE warehouse OWNER warehouse;

\connect warehouse;

-- Grant
GRANT ALL PRIVILEGES ON DATABASE warehouse TO warehouse;
GRANT ALL ON SCHEMA public TO warehouse;

-- Comexstat pre-computed tables
CREATE TABLE IF NOT EXISTS comexstat_summary (
    period_type     VARCHAR(30)  NOT NULL,
    period_label    VARCHAR(50)  NOT NULL,
    export_fob      NUMERIC(20,2),
    import_fob      NUMERIC(20,2),
    balance         NUMERIC(20,2),
    export_growth   NUMERIC(10,4),
    import_growth   NUMERIC(10,4),
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (period_type, period_label)
);

CREATE TABLE IF NOT EXISTS comexstat_summary_history (
    year            INTEGER NOT NULL,
    month           INTEGER NOT NULL,
    export_fob      NUMERIC(20,2),
    import_fob      NUMERIC(20,2),
    balance         NUMERIC(20,2),
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (year, month)
);

CREATE TABLE IF NOT EXISTS comexstat_timeseries (
    periodicity     VARCHAR(10)  NOT NULL,  -- 'monthly' | 'annual'
    series          VARCHAR(10)  NOT NULL,  -- 'export' | 'import' | 'balance'
    year            INTEGER      NOT NULL,
    month           INTEGER,
    value           NUMERIC(20,2),
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (periodicity, series, year, month)
);

CREATE TABLE IF NOT EXISTS comexstat_partners (
    flow            VARCHAR(10)  NOT NULL,
    period_from     VARCHAR(8)   NOT NULL,
    period_to       VARCHAR(8)   NOT NULL,
    country_code    VARCHAR(10)  NOT NULL,
    country_name    VARCHAR(200),
    fob_value       NUMERIC(20,2),
    share           NUMERIC(10,4),
    ranking         INTEGER,
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flow, period_from, period_to, country_code)
);

CREATE TABLE IF NOT EXISTS comexstat_products (
    flow            VARCHAR(10)  NOT NULL,
    periodicity     VARCHAR(10)  NOT NULL,
    period_from     VARCHAR(8)   NOT NULL,
    period_to       VARCHAR(8)   NOT NULL,
    aggregation     VARCHAR(10)  NOT NULL,  -- 'ncm' | 'heading' | 'chapter'
    code            VARCHAR(20)  NOT NULL,
    description     TEXT,
    fob_value       NUMERIC(20,2),
    weight_kg       NUMERIC(20,2),
    share           NUMERIC(10,4),
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flow, periodicity, period_from, period_to, aggregation, code)
);

CREATE TABLE IF NOT EXISTS comexstat_national (
    flow            VARCHAR(10)  NOT NULL,
    period_from     VARCHAR(8)   NOT NULL,
    period_to       VARCHAR(8)   NOT NULL,
    ceara_fob       NUMERIC(20,2),
    brazil_fob      NUMERIC(20,2),
    ceara_share     NUMERIC(10,4),
    ceara_rank      INTEGER,
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flow, period_from, period_to)
);

CREATE TABLE IF NOT EXISTS comexstat_states_ranking (
    flow            VARCHAR(10)  NOT NULL,
    period_from     VARCHAR(8)   NOT NULL,
    period_to       VARCHAR(8)   NOT NULL,
    state_code      VARCHAR(5)   NOT NULL,
    state_name      VARCHAR(100),
    fob_value       NUMERIC(20,2),
    share           NUMERIC(10,4),
    ranking         INTEGER,
    sectors         JSONB,
    top_partners    JSONB,
    top_products    JSONB,
    updated_at      TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (flow, period_from, period_to, state_code)
);

-- RDE pre-computed tables
CREATE TABLE IF NOT EXISTS rde_todos_registros (
    codigo_rde              VARCHAR(50)   PRIMARY KEY,
    nome_pessoa_nacional     VARCHAR(500),
    uf_pessoa_nacional       VARCHAR(5),
    nome_pessoa_estrangeira  VARCHAR(500),
    pais_pessoa_estrangeira  VARCHAR(200),
    moeda_operacao           VARCHAR(20),
    valor_operacao           NUMERIC(20,2),
    sistema                  VARCHAR(50),
    ocorrencia               VARCHAR(200),
    modalidade               VARCHAR(200),
    ano                      INTEGER,
    mes                      INTEGER,
    updated_at               TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rde_todos_ano_mes ON rde_todos_registros (ano DESC, mes DESC);
CREATE INDEX IF NOT EXISTS idx_rde_todos_uf ON rde_todos_registros (uf_pessoa_nacional);

CREATE TABLE IF NOT EXISTS rde_registros_ied (
    codigo_rde              VARCHAR(50)   PRIMARY KEY,
    cnpj_base_receptora     VARCHAR(20),
    nome_pessoa_nacional     VARCHAR(500),
    uf_pessoa_nacional       VARCHAR(5),
    nome_pessoa_estrangeira  VARCHAR(500),
    pais_pessoa_estrangeira  VARCHAR(200),
    moeda_operacao           VARCHAR(20),
    valor_operacao           NUMERIC(20,2),
    sistema                  VARCHAR(50),
    ocorrencia               VARCHAR(200),
    modalidade               VARCHAR(200),
    ano                      INTEGER,
    mes                      INTEGER,
    updated_at               TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rde_ied_ano_mes ON rde_registros_ied (ano DESC, mes DESC);

-- SCM tables (mirror das entities existentes, agora em PostgreSQL)
CREATE TABLE IF NOT EXISTS scm_fases (
    id_fase_processo    INTEGER PRIMARY KEY,
    ds_fase_processo    VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS scm_tipos (
    id_tipo_requerimento    INTEGER PRIMARY KEY,
    ds_tipo_requerimento    VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS scm_municipios (
    id_municipio    INTEGER PRIMARY KEY,
    nm_municipio    VARCHAR(200),
    sg_uf           VARCHAR(2)
);
CREATE INDEX IF NOT EXISTS idx_scm_municipios_uf ON scm_municipios (sg_uf);

CREATE TABLE IF NOT EXISTS scm_substancias (
    id_substancia    INTEGER PRIMARY KEY,
    nm_substancia    VARCHAR(200)
);

CREATE TABLE IF NOT EXISTS scm_processos (
    ds_processo                         VARCHAR(50)  PRIMARY KEY,
    nr_processo                         VARCHAR(20),
    nr_ano_processo                     VARCHAR(4),
    bt_ativo                            VARCHAR(1),
    nr_nup                              VARCHAR(100),
    id_tipo_requerimento                INTEGER REFERENCES scm_tipos(id_tipo_requerimento),
    id_fase_processo                    INTEGER REFERENCES scm_fases(id_fase_processo),
    id_unidade_administrativa_regional  INTEGER,
    id_unidade_protocolizadora          INTEGER,
    dt_protocolo                        VARCHAR(30),
    dt_prioridade                       VARCHAR(30),
    qt_area_ha                          VARCHAR(20),
    updated_at                          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_scm_processos_fase ON scm_processos (id_fase_processo);
CREATE INDEX IF NOT EXISTS idx_scm_processos_tipo ON scm_processos (id_tipo_requerimento);

CREATE TABLE IF NOT EXISTS scm_processo_municipio (
    ds_processo     VARCHAR(50)  NOT NULL REFERENCES scm_processos(ds_processo) ON DELETE CASCADE,
    id_municipio    INTEGER      NOT NULL REFERENCES scm_municipios(id_municipio),
    PRIMARY KEY (ds_processo, id_municipio)
);
CREATE INDEX IF NOT EXISTS idx_scm_pm_municipio ON scm_processo_municipio (id_municipio);
CREATE INDEX IF NOT EXISTS idx_scm_pm_processo ON scm_processo_municipio (ds_processo);

CREATE TABLE IF NOT EXISTS scm_processo_substancia (
    ds_processo                         VARCHAR(50)  NOT NULL,
    id_substancia                       INTEGER      NOT NULL,
    id_tipo_uso_substancia              INTEGER,
    id_motivo_encerramento_substancia   INTEGER,
    PRIMARY KEY (ds_processo, id_substancia)
);
CREATE INDEX IF NOT EXISTS idx_scm_ps_substancia ON scm_processo_substancia (id_substancia);

-- Sigmine GeoJSON layers
CREATE TABLE IF NOT EXISTS sigmine_layers (
    layer_name  VARCHAR(50)  PRIMARY KEY,
    geojson     JSONB        NOT NULL,
    feature_count INTEGER,
    updated_at  TIMESTAMP DEFAULT NOW()
);

GRANT ALL ON ALL TABLES IN SCHEMA public TO warehouse;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO warehouse;
