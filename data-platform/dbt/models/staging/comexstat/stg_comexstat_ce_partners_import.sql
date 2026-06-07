{{ config(materialized='view', schema='staging') }}
SELECT year, country, metric_fob, metric_cif
FROM raw.comexstat_ce_import_partners
WHERE year IS NOT NULL AND country != ''
