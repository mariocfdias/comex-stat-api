{{
    config(
        materialized='view',
        schema='staging'
    )
}}

SELECT
    pm.processo_numero,
    pm.municipio_id,
    m.nome AS municipio_nome,
    m.sguf AS municipio_uf
FROM {{ source('raw_scm', 'scm_processo_municipio') }} pm
LEFT JOIN {{ source('raw_scm', 'scm_municipio') }} m ON pm.municipio_id = m.id
