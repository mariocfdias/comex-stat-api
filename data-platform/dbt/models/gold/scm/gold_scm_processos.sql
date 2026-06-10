{{
    config(
        materialized='table',
        schema='gold'
    )
}}

-- Tabela principal de processos SCM com dimensões expandidas
-- Substituível pelo SELECT direto em raw.scm_processo (JOIN nas dimensões)
SELECT
    p.numero,
    p.nome,
    p.fase_id,
    p.fase_nome,
    p.tipo_id,
    p.tipo_nome,
    p.area_ha,
    p.uf,
    p.data_ultimo_evento,
    p.data_validade,
    p.ultimo_evento,
    -- Municípios como array JSON
    COALESCE(
        (SELECT json_agg(json_build_object('id', m.municipio_id, 'nome', m.municipio_nome))
         FROM {{ ref('stg_scm_processos_municipios') }} m WHERE m.processo_numero = p.numero),
        '[]'
    ) AS municipios,
    -- Substâncias como array JSON
    COALESCE(
        (SELECT json_agg(json_build_object('id', s.substancia_id, 'nome', s.substancia_nome))
         FROM {{ ref('stg_scm_processos_substancias') }} s WHERE s.processo_numero = p.numero),
        '[]'
    ) AS substancias
FROM {{ ref('stg_scm_processos') }} p
