#!/bin/bash
# =============================================================================
# init_airflow_db.sh (prefixo 00_ para executar ANTES do init_postgres.sql)
# Cria o banco de dados exclusivo do Airflow e seu usuário.
# O PostgreSQL executa scripts em ordem lexicográfica dentro de
# /docker-entrypoint-initdb.d/ — por isso o prefixo 00_ garante que
# este script roda antes do 01_init.sql.
# =============================================================================
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE airflow;
    CREATE USER airflow WITH PASSWORD 'airflow';
    GRANT ALL PRIVILEGES ON DATABASE airflow TO airflow;
EOSQL

echo "Banco 'airflow' e usuário criados com sucesso."
