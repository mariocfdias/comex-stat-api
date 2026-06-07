{{
    config(
        materialized='table',
        schema='gold'
    )
}}

SELECT
    p.tipo_id,
    t.nome AS tipo_nome,
    COUNT(*) AS total_processos,
    COALESCE(SUM(p.area_ha), 0) AS area_total_ha,
    ROUND(COALESCE(AVG(p.area_ha), 0), 2) AS area_media_ha
FROM {{ ref('stg_scm_processos') }} p
LEFT JOIN {{ source('raw_scm', 'scm_tipo_requerimento') }} t ON p.tipo_id = t.id
GROUP BY p.tipo_id, t.nome
ORDER BY total_processos DESC
