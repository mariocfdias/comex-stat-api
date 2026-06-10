-- =============================================================================
-- init_postgres.sql
-- Executado automaticamente pelo PostgreSQL na primeira inicialização do container.
-- Cria: extensões, banco da plataforma, schemas, usuários e permissões.
-- =============================================================================

-- Extensão geoespacial (necessária para dados do Sigmine)
CREATE EXTENSION IF NOT EXISTS postgis;

-- -----------------------------------------------------------------------------
-- Banco exclusivo do Airflow (metadados internos do orquestrador)
-- -----------------------------------------------------------------------------
CREATE DATABASE airflow;

-- -----------------------------------------------------------------------------
-- Banco da plataforma de dados
-- -----------------------------------------------------------------------------
\c comexstat_platform

CREATE EXTENSION IF NOT EXISTS postgis;

-- Schemas do lakehouse
CREATE SCHEMA IF NOT EXISTS raw;      -- dados brutos ingeridos das fontes
CREATE SCHEMA IF NOT EXISTS staging;  -- dados limpos, tipados e normalizados
CREATE SCHEMA IF NOT EXISTS gold;     -- tabelas pré-agregadas prontas para a API

-- -----------------------------------------------------------------------------
-- Usuário da API: somente leitura no schema gold
-- Usado pela FastAPI para servir endpoints
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'api_reader') THEN
        CREATE USER api_reader WITH PASSWORD 'api_reader_pass';
    END IF;
END
$$;

GRANT USAGE ON SCHEMA gold TO api_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO api_reader;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO api_reader;

-- -----------------------------------------------------------------------------
-- Usuário do dbt: leitura/escrita em raw, staging e gold
-- Usado pelos pipelines Airflow para transformações
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'dbt_user') THEN
        CREATE USER dbt_user WITH PASSWORD 'dbt_user_pass';
    END IF;
END
$$;

GRANT ALL ON SCHEMA raw, staging, gold TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw     GRANT ALL ON TABLES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON TABLES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold    GRANT ALL ON TABLES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA raw     GRANT ALL ON SEQUENCES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON SEQUENCES TO dbt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold    GRANT ALL ON SEQUENCES TO dbt_user;
