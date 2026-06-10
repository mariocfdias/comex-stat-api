{{
    config(
        materialized='view',
        schema='staging'
    )
}}

SELECT
    ps.processo_numero,
    ps.substancia_id,
    s.nome AS substancia_nome
FROM {{ source('raw_scm', 'scm_processo_substancia') }} ps
LEFT JOIN {{ source('raw_scm', 'scm_substancia') }} s ON ps.substancia_id = s.id
