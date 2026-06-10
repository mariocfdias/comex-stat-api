{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Painel consolidado — une summary + top partners + top products em uma linha por período
-- Substitui: ComexstatService.getDashboardData() que fazia múltiplas queries em paralelo
WITH summary_ytd AS (
    SELECT * FROM gold.gold_comexstat_summary
    WHERE period_type = 'year_to_date'
),

top_partners AS (
    SELECT json_agg(
        json_build_object(
            'country', country,
            'exports', exports_fob,
            'imports', imports_fob,
            'current', current,
            'percentage', percentage
        ) ORDER BY rank
    ) AS partners_json
    FROM gold.gold_comexstat_partners
    WHERE period_type = 'year_to_date' AND flow = 'total' AND rank <= 5
),

top_products AS (
    SELECT json_agg(
        json_build_object(
            'code', code,
            'description', description,
            'value', value_fob,
            'percentage', percentage
        ) ORDER BY rank
    ) AS products_json
    FROM gold.gold_comexstat_products
    WHERE period_type = 'year_to_date' AND flow = 'export' AND aggregation_level = 'heading' AND rank <= 10
)

SELECT
    s.period_type,
    s.period_from,
    s.period_to,
    s.period_label,
    s.exports_fob,
    s.imports_fob,
    s.trade_balance,
    s.trade_current,
    s.export_participation,
    s.import_participation,
    s.export_ranking,
    s.import_ranking,
    p.partners_json AS top_export_partners,
    pr.products_json AS top_export_products,
    NOW() AS generated_at
FROM summary_ytd s
CROSS JOIN top_partners p
CROSS JOIN top_products pr
