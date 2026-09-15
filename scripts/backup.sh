#!/usr/bin/env bash
# backup.sh - Script de backup para Neo RX
# Uso: ./backup.sh [full|incremental] [retention_days]

set -euo pipefail

BACKUP_TYPE=${1:-full}
RETENTION_DAYS=${2:-30}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/neorx"
CONTAINER_POSTGRES="neorx-postgres"
CONTAINER_REDIS="neorx-redis"

mkdir -p "${BACKUP_DIR}"

echo "============================================================"
echo "Neo RX - Backup ${BACKUP_TYPE} - $(date)"
echo "============================================================"

# Función para limpiar backups antiguos
cleanup_old_backups() {
    echo "Limpiando backups mayores a ${RETENTION_DAYS} días..."
    find "${BACKUP_DIR}" -type f -name "neorx_*.sql.gz" -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -type f -name "neorx_*.rdb" -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -type f -name "neorx_media_*.tar.gz" -mtime +${RETENTION_DAYS} -delete
    echo "Limpieza completada"
}

# Backup de PostgreSQL
backup_postgres() {
    local suffix=$1
    local output_file="${BACKUP_DIR}/neorx_${suffix}_${TIMESTAMP}.sql.gz"

    echo "Backup de PostgreSQL (${suffix})..."
    docker exec "${CONTAINER_POSTGRES}" pg_dump \
        -U "${POSTGRES_USER:-neorx}" \
        -d "${POSTGRES_DB:-neorx}" \
        --no-owner --no-acl \
        --clean --if-exists \
        | gzip -9 > "${output_file}"

    if [[ -f "${output_file}" && -s "${output_file}" ]]; then
        local size=$(du -h "${output_file}" | cut -f1)
        echo "✓ PostgreSQL backup: ${output_file} (${size})"
    else
        echo "ERROR: Backup de PostgreSQL falló"
        exit 1
    fi
}

# Backup de Redis (RDB snapshot)
backup_redis() {
    local output_file="${BACKUP_DIR}/neorx_redis_${TIMESTAMP}.rdb"

    echo "Backup de Redis..."
    # Forzar BGSAVE y esperar
    docker exec "${CONTAINER_REDIS}" redis-cli BGSAVE
    # Esperar a que termine
    while docker exec "${CONTAINER_REDIS}" redis-cli LASTSAVE | grep -q "$(docker exec "${CONTAINER_REDIS}" redis-cli LASTSAVE)"; do
        sleep 1
    done
    # Copiar dump.rdb
    docker cp "${CONTAINER_REDIS}":/data/dump.rdb "${output_file}"

    if [[ -f "${output_file}" && -s "${output_file}" ]]; then
        local size=$(du -h "${output_file}" | cut -f1)
        echo "✓ Redis backup: ${output_file} (${size})"
    else
        echo "WARNING: Backup de Redis falló o está vacío"
    fi
}

# Backup de archivos media
backup_media() {
    local output_file="${BACKUP_DIR}/neorx_media_${TIMESTAMP}.tar.gz"

    echo "Backup de archivos media..."
    docker run --rm \
        -v neorx_media_files:/media:ro \
        -v "${BACKUP_DIR}":/backup \
        alpine tar -czf "/backup/$(basename "${output_file}")" -C /media .

    if [[ -f "${output_file}" && -s "${output_file}" ]]; then
        local size=$(du -h "${output_file}" | cut -f1)
        echo "✓ Media backup: ${output_file} (${size})"
    else
        echo "WARNING: Backup de media falló"
    fi
}

# Verificar integridad del backup
verify_backup() {
    local file=$1
    echo "Verificando integridad de $(basename "${file}")..."

    if [[ "${file}" == *.sql.gz ]]; then
        gzip -t "${file}" && echo "✓ Integridad OK" || { echo "ERROR: Archivo corrupto"; exit 1; }
    elif [[ "${file}" == *.tar.gz ]]; then
        tar -tzf "${file}" > /dev/null && echo "✓ Integridad OK" || { echo "ERROR: Archivo corrupto"; exit 1; }
    fi
}

# Main
case "${BACKUP_TYPE}" in
    full)
        backup_postgres "full"
        backup_redis
        backup_media
        cleanup_old_backups
        ;;
    incremental)
        backup_postgres "inc"
        # Redis y media solo en full
        cleanup_old_backups
        ;;
    *)
        echo "Uso: $0 [full|incremental] [retention_days]"
        exit 1
        ;;
esac

# Verificar todos los backups generados
for f in "${BACKUP_DIR}"/*_${TIMESTAMP}.*; do
    [[ -f "${f}" ]] && verify_backup "${f}"
done

echo ""
echo "============================================================"
echo "Backup ${BACKUP_TYPE} completado exitosamente"
echo "Archivos en: ${BACKUP_DIR}"
ls -lh "${BACKUP_DIR}"/*_${TIMESTAMP}.*
echo "============================================================"