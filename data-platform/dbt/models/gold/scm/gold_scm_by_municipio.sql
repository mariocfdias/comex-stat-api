{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Processos por município (via tabela de relação N:N)
SELECT
    pm.municipio_id,
    pm.municipio_nome,
    COUNT(DISTINCT pm.processo_numero) AS total_processos,
    COALESCE(SUM(p.area_ha), 0) AS area_total_ha
FROM {{ ref('stg_scm_processos_municipios') }} pm
LEFT JOIN {{ source('raw_scm', 'scm_processo') }} p ON pm.processo_numero = p.numero
GROUP BY pm.municipio_id, pm.municipio_nome
ORDER BY total_processos DESC
