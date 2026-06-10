{{ config(materialized='view', schema='staging') }}
SELECT year, ncm_code, ncm, metric_fob, metric_kg
FROM raw.comexstat_ce_import_ncm
WHERE year IS NOT NULL AND ncm_code != ''
