{{ config(materialized='view', schema='staging') }}
SELECT year, month, metric_fob, metric_cif
FROM raw.comexstat_national_import_total
WHERE year IS NOT NULL AND month BETWEEN 1 AND 12
