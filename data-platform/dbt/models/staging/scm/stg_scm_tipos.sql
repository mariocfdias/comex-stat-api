{{ config(materialized='view', schema='staging') }}
SELECT id, nome FROM {{ source('raw_scm', 'scm_tipo_requerimento') }}
