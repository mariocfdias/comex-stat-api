{{ config(materialized='view', schema='staging') }}
SELECT year, heading_code, heading, chapter_code, chapter, metric_fob, metric_kg
FROM raw.comexstat_ce_export_heading
WHERE year IS NOT NULL AND heading_code != ''
