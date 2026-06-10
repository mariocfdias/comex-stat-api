{{ config(materialized='view', schema='staging') }}
SELECT year, month, state, metric_fob, metric_cif
FROM raw.comexstat_national_import_states
WHERE year IS NOT NULL AND state != ''
