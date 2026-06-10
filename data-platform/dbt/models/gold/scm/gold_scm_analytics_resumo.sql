{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Resumo executivo dos processos minerais do Ceará
SELECT
    COUNT(*) AS total_processos,
    COUNT(DISTINCT fase_id) AS total_fases,
    COUNT(DISTINCT tipo_id) AS total_tipos,
    COALESCE(SUM(area_ha), 0) AS area_total_ha,
    ROUND(COALESCE(AVG(area_ha), 0), 2) AS area_media_ha,
    MAX(data_ultimo_evento) AS ultimo_evento_data
FROM {{ ref('stg_scm_processos') }}
