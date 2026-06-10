{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Resumo anual de registros RDE do Ceará
SELECT
    "Ano",
    "Sistema",
    COUNT(*) AS total_registros,
    COUNT(DISTINCT "NomePessoaNacional") AS empresas_distintas,
    COUNT(DISTINCT "PaisPessoaEstrangeira") AS paises_distintos,
    COALESCE(SUM("ValorOperacao"), 0) AS valor_total_operacoes
FROM gold.gold_rde_todos_registros
WHERE "Ano" IS NOT NULL
GROUP BY "Ano", "Sistema"
ORDER BY "Ano" DESC, total_registros DESC
