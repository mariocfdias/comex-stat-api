{{ config(materialized='view', schema='staging') }}
SELECT id, nome FROM {{ source('raw_scm', 'scm_fase_processo') }}
