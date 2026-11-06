# Despliegue de NeoRX con Docker

## Componentes

El despliegue ejecuta PostgreSQL 16, Redis 7, migraciones y archivos estáticos,
Django con Gunicorn, un trabajador Celery dedicado a inferencia, Celery Beat y
el frontend React servido por Nginx. El modelo se monta en modo de solo lectura
desde `backend/models/neorx_effusion_categories_resnet50.pt`.

## Inicio rápido en Windows

Requisitos: Docker Desktop abierto y el checkpoint en la ruta indicada. Desde
la raíz del proyecto:

```powershell
.\scripts\setup-docker.ps1
docker compose --env-file .env.docker -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.docker -f docker-compose.prod.yml ps -a
```

El script genera claves únicas para Django, Fernet y PostgreSQL, crea
`.env.docker` y no sobrescribe un archivo existente. La aplicación se abre en:

```text
http://localhost:8080
```

Las credenciales de demostración predeterminadas son:

| Rol | Usuario | Contraseña |
|---|---|---|
| Administrador | `admin` | `Admin123!` |
| Médico | `medico` | `Medico123!` |
| Recepción | `recepcionista` | `Recepcionista123!` |

Estas cuentas se destinan a la defensa local. Antes de un despliegue real,
establece `NEORX_CREATE_DEMO_USERS=false`, cambia las contraseñas y crea las
cuentas mediante un canal administrativo seguro.

## Comprobaciones

```powershell
curl.exe http://localhost:8080/health/
docker compose --env-file .env.docker -f docker-compose.prod.yml logs --tail 100 migrate backend celery_worker frontend
docker compose --env-file .env.docker -f docker-compose.prod.yml exec -T backend python manage.py check
```

El estado correcto muestra PostgreSQL, Redis, backend, frontend y trabajador
Celery activos; `migrate` debe aparecer como `Exited (0)`. En los registros del
trabajador debe figurar la carga del checkpoint fine-tuned y cinco clases.

## Operación

```powershell
# Ver estado
docker compose --env-file .env.docker -f docker-compose.prod.yml ps -a

# Ver registros en tiempo real
docker compose --env-file .env.docker -f docker-compose.prod.yml logs -f backend celery_worker frontend

# Reiniciar servicios
docker compose --env-file .env.docker -f docker-compose.prod.yml restart

# Detener sin borrar datos
docker compose --env-file .env.docker -f docker-compose.prod.yml down
```

No agregues `-v` al comando `down` si deseas conservar la base, Redis, imágenes,
estáticos y registros. Los datos persistentes viven en volúmenes nombrados.

## HTTPS para servidor

El servicio TLS es opcional. Instala `ssl/fullchain.pem` y `ssl/privkey.pem`,
configura en `.env.docker` el dominio permitido, el origen CORS HTTPS,
`SECURE_SSL_REDIRECT=True` y un valor HSTS adecuado. Después ejecuta:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml --profile tls up -d
```

No actives HSTS ni redirección SSL en la demostración HTTP local. Para Internet,
usa certificados válidos, contraseñas nuevas, firewall, copias de seguridad y
una revisión de privacidad de los datos clínicos.
