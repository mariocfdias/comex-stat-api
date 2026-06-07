{{ config(materialized='view', schema='staging') }}
SELECT year, month, state, metric_fob
FROM raw.comexstat_national_export_states
WHERE year IS NOT NULL AND state != ''
