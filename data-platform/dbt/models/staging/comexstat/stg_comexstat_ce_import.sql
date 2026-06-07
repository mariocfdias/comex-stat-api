{{ config(materialized='view', schema='staging') }}

SELECT year, month, country, isic_section_code, isic_section,
       heading_code, heading, metric_fob, metric_cif, metric_kg
FROM raw.comexstat_ce_import_monthly
WHERE year IS NOT NULL AND month BETWEEN 1 AND 12
