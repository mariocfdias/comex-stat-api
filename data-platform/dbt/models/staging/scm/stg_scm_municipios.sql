{{ config(materialized='view', schema='staging') }}
SELECT id, nome, sguf FROM {{ source('raw_scm', 'scm_municipio') }}
