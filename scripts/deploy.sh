#!/usr/bin/env bash
# deploy.sh - Script de despliegue para Neo RX
# Uso: ./deploy.sh [staging|production]

set -euo pipefail

ENVIRONMENT=${1:-production}
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.${ENVIRONMENT}"

echo "============================================================"
echo "Neo RX - Despliegue ${ENVIRONMENT}"
echo "============================================================"

# Verificar archivo de entorno
if [[ ! -f "${ENV_FILE}" ]]; then
    echo "ERROR: Archivo ${ENV_FILE} no encontrado"
    echo "Crea ${ENV_FILE} basado en .env.example"
    exit 1
fi

# Cargar variables de entorno
set -a
source "${ENV_FILE}"
set +a

# Verificar variables críticas
REQUIRED_VARS=("SECRET_KEY" "FERNET_KEY" "POSTGRES_PASSWORD" "CORS_ALLOWED_ORIGINS")
for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "ERROR: Variable requerida ${var} no definida en ${ENV_FILE}"
        exit 1
    fi
done

# Generar FERNET_KEY si no existe
if [[ -z "${FERNET_KEY}" ]]; then
    echo "Generando FERNET_KEY..."
    export FERNET_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
    echo "FERNET_KEY=${FERNET_KEY}" >> "${ENV_FILE}"
fi

# Función para verificar salud de servicios
check_health() {
    local service=$1
    local max_attempts=30
    local attempt=1

    echo "Esperando a que ${service} esté saludable..."
    while [[ $attempt -le $max_attempts ]]; do
        if docker compose -f "${COMPOSE_FILE}" ps "${service}" | grep -q "healthy"; then
            echo "✓ ${service} está saludable"
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    echo "ERROR: ${service} no se volvió saludable después de $((max_attempts * 2)) segundos"
    return 1
}

# 1. Build imágenes
echo "[1/7] Construyendo imágenes Docker..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" build --parallel

# 2. Levantar base de datos y Redis
echo "[2/7] Iniciando PostgreSQL y Redis..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d postgres redis

# Esperar a que estén listos
check_health postgres
check_health redis

# 3. Ejecutar migraciones
echo "[3/7] Ejecutando migraciones Django..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm backend python manage.py migrate --noinput

# 4. Recopilar archivos estáticos
echo "[4/7] Recopilando archivos estáticos..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm backend python manage.py collectstatic --noinput

# 5. Crear superusuario si no existe
echo "[5/7] Verificando superusuario..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" run --rm backend python manage.py shell -c "
from accounts.models import CustomUser
if not CustomUser.objects.filter(username='admin').exists():
    CustomUser.objects.create_superuser('admin', 'admin@neorx.local', 'admin123', rol='administrador')
    print('Superusuario admin creado')
else:
    print('Superusuario ya existe')
"

# 6. Levantar todos los servicios
echo "[6/7] Iniciando todos los servicios..."
docker compose -f "${COMPOSE_FILE}" --env-file "${ENV_FILE}" up -d

# Esperar a que todos estén saludables
for service in backend celery_worker celery_beat frontend nginx; do
    check_health "${service}"
done

# 7. Verificación final
echo "[7/7] Verificación final..."
sleep 5

# Test endpoints críticos
echo "Probando endpoints..."
curl -sf http://localhost/health > /dev/null && echo "✓ Frontend OK" || echo "✗ Frontend FAIL"
curl -sf http://localhost/api/token/ -X POST -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' > /dev/null && echo "✓ Auth API OK" || echo "✗ Auth API FAIL"
curl -sf -H "Authorization: Bearer $(curl -s http://localhost/api/token/ -X POST -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}' | jq -r .access)" http://localhost/api/pacientes/ > /dev/null && echo "✓ Pacientes API OK" || echo "✗ Pacientes API FAIL"

echo ""
echo "============================================================"
echo "Despliegue ${ENVIRONMENT} completado"
echo "============================================================"
echo "Frontend:      http://localhost (HTTP) / https://localhost (HTTPS)"
echo "API Docs:      http://localhost/api/schema/swagger/"
echo "Admin Django:  http://localhost/admin/"
echo "Credenciales:  admin / admin123 (cambiar en producción)"
echo ""
echo "Para ver logs: docker compose -f ${COMPOSE_FILE} logs -f [servicio]"
echo "Para parar:    docker compose -f ${COMPOSE_FILE} down"
echo "============================================================"