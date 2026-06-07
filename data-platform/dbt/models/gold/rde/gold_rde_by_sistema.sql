{{
    config(
        materialized='table',
        schema='gold'
    )
}}

SELECT
    "Sistema",
    COUNT(*) AS total_registros,
    MIN("Ano") AS ano_inicio,
    MAX("Ano") AS ano_fim,
    COUNT(DISTINCT "Ano" || '-' || "Mes") AS meses_distintos
FROM gold.gold_rde_todos_registros
WHERE "Sistema" IS NOT NULL
GROUP BY "Sistema"
ORDER BY total_registros DESC
