{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Exportações do Ceará com dados mensais — base para summary, timeseries e partners
-- Origem: raw.comexstat_ce_export_monthly carregado pelo DAG
SELECT
    year,
    month,
    country,
    isic_section_code,
    isic_section,
    heading_code,
    heading,
    metric_fob,
    metric_kg
FROM raw.comexstat_ce_export_monthly
WHERE year IS NOT NULL AND month BETWEEN 1 AND 12
