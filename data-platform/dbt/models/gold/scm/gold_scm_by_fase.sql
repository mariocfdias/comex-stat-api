{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Replica ScmService.getProcessosByFase() — agrupamento por fase
SELECT
    p.fase_id,
    f.nome AS fase_nome,
    COUNT(*) AS total_processos,
    COALESCE(SUM(p.area_ha), 0) AS area_total_ha,
    ROUND(COALESCE(AVG(p.area_ha), 0), 2) AS area_media_ha
FROM {{ ref('stg_scm_processos') }} p
LEFT JOIN {{ source('raw_scm', 'scm_fase_processo') }} f ON p.fase_id = f.id
GROUP BY p.fase_id, f.nome
ORDER BY total_processos DESC
