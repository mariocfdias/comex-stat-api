{{ config(materialized='view', schema='staging') }}
SELECT year, country, metric_fob
FROM raw.comexstat_ce_export_partners
WHERE year IS NOT NULL AND country != ''
