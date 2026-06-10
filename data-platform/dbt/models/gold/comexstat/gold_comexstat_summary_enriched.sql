{{
    config(
        materialized='view',
        schema='gold'
    )
}}

-- View enriquecida do summary — adiciona campos calculados que o NestJS derivava em memória
SELECT
    period_type,
    period_from,
    period_to,
    period_label,
    exports_fob,
    imports_fob,
    trade_balance,
    trade_current,
    export_participation,
    import_participation,
    export_ranking,
    import_ranking,
    -- Campo calculado: percentual de participação do CE no comércio nacional
    CASE
        WHEN trade_current > 0 THEN ROUND(exports_fob / trade_current * 100, 2)
        ELSE 0
    END AS export_share_of_current,
    NOW() AS generated_at
FROM gold.gold_comexstat_summary
