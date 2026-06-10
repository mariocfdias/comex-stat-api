{{
    config(
        materialized='table',
        schema='gold'
    )
}}

SELECT
    ps.substancia_id,
    ps.substancia_nome,
    COUNT(DISTINCT ps.processo_numero) AS total_processos,
    COALESCE(SUM(p.area_ha), 0) AS area_total_ha
FROM {{ ref('stg_scm_processos_substancias') }} ps
LEFT JOIN {{ source('raw_scm', 'scm_processo') }} p ON ps.processo_numero = p.numero
GROUP BY ps.substancia_id, ps.substancia_nome
ORDER BY total_processos DESC
