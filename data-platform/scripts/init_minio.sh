#!/bin/sh
# =============================================================================
# init_minio.sh
# Executado pelo container minio-init para criar os buckets iniciais.
# =============================================================================

set -e

MINIO_ENDPOINT="${MINIO_ENDPOINT:-minio:9000}"
MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin123}"

echo "Aguardando MinIO ficar disponível em http://${MINIO_ENDPOINT}..."
until mc alias set local "http://${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}" 2>/dev/null; do
    echo "MinIO ainda não disponível. Aguardando 3s..."
    sleep 3
done

echo "MinIO disponível. Criando buckets..."

# Camada Bronze: dados brutos das fontes (ComexStat JSON, RDE JSON, SCM CSV/ZIP, Sigmine SHP)
mc mb --ignore-existing local/raw-data
mc anonymous set none local/raw-data

# Camada Silver: dados limpos em Parquet, particionados por data
mc mb --ignore-existing local/staging-data
mc anonymous set none local/staging-data

# Backups e arquivamento
mc mb --ignore-existing local/backups
mc anonymous set none local/backups

echo "Buckets criados com sucesso:"
mc ls local/

# Criar estrutura de prefixos para cada fonte de dados
echo "Configurando estrutura de prefixos..."
echo "placeholder" | mc pipe local/raw-data/comexstat/.keep
echo "placeholder" | mc pipe local/raw-data/rde/.keep
echo "placeholder" | mc pipe local/raw-data/scm/.keep
echo "placeholder" | mc pipe local/raw-data/sigmine/.keep
echo "placeholder" | mc pipe local/staging-data/comexstat/.keep
echo "placeholder" | mc pipe local/staging-data/rde/.keep
echo "placeholder" | mc pipe local/staging-data/scm/.keep
echo "placeholder" | mc pipe local/staging-data/sigmine/.keep

echo "Inicialização do MinIO concluída."
