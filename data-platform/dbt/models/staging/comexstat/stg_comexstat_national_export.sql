{{ config(materialized='view', schema='staging') }}
-- Total nacional de exportações com detalhes mensais (monthDetail=True)
-- Usado para calcular participação do CE no total nacional com precisão mensal
SELECT year, month, metric_fob
FROM raw.comexstat_national_export_total
WHERE year IS NOT NULL AND month BETWEEN 1 AND 12
