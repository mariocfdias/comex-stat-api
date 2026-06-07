{{
    config(
        materialized='view',
        schema='staging'
    )
}}

-- Processos SCM com fase e tipo desnormalizados
-- Fonte: raw.scm_processo + raw.scm_fase_processo + raw.scm_tipo_requerimento
SELECT
    p.numero,
    p.fase_id,
    f.nome AS fase_nome,
    p.tipo_id,
    t.nome AS tipo_nome,
    p.area_ha,
    p.uf,
    p.nome,
    p.data_ultimo_evento,
    p.data_validade,
    p.ultimo_evento
FROM {{ source('raw_scm', 'scm_processo') }} p
LEFT JOIN {{ source('raw_scm', 'scm_fase_processo') }} f ON p.fase_id = f.id
LEFT JOIN {{ source('raw_scm', 'scm_tipo_requerimento') }} t ON p.tipo_id = t.id
