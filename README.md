# Neo RX

Sistema web de gestión radiológica con pacientes, estudios, análisis asistido por una CNN para radiografías de tórax, informes radiológicos y administración por roles.

La salida del modelo es apoyo para revisión profesional. No sustituye el diagnóstico ni la firma de un médico radiólogo.

## Funciones disponibles

- Autenticación JWT con renovación, cierre de sesión, roles y opción de recordar sesión.
- Recuperación de contraseña mediante código de seis dígitos enviado al correo registrado.
- CRUD de pacientes y usuarios, filtros, paginación y auditoría de actividad.
- Registro de radiografías no torácicas sin ejecutar la CNN.
- Carga de DICOM, PNG, JPEG, WebP, TIFF y BMP; previsualización PNG, zoom y validación técnica.
- Modo temporal operativo con ResNet-50 preentrenada: derrame pleural es el único hallazgo específico presentado; si no alcanza 0,50, el sistema ofrece como máximo una categoría tumoral, pleural, infecciosa o intersticial. Atelectasia se omite de la conclusión para reducir ambigüedad. El entrenamiento futuro queda preparado en [auditoría y entrenamiento priority2](docs/entrenamiento-priority2.md).
- Grad-CAM bajo demanda y resultados conservados por estudio.
- Procesamiento en segundo plano con cola local sin Redis (`thread`), o Celery/Redis cuando se configura explícitamente.
- Reintento de imágenes fallidas desde el estudio, sin duplicar la carga; informes firmados protegidos.
- Informes estructurados, borrador, revisión, firma médica, PDF y DICOM SR.
- Al terminar un análisis, abre su informe y usa «Descargar preinforme (PDF)». El archivo conserva el estado sin firma e incorpora la imagen de origen como anexo; los cambios del editor deben guardarse antes de descargar. Después de la revisión y firma médica se habilita la exportación definitiva. El PDF de borrador utiliza `GET /api/informes/{id}/pdf/?borrador=1` para médico o administrador; DICOM SR mantiene el requisito de firma.
- Tableros operativos, métricas, temas visuales y navegación adaptada por rol.
- API OpenAPI con Swagger y ReDoc.
- Despliegue reproducible con Docker Compose, PostgreSQL, Redis, Django, Celery y Nginx.

## Requisitos

Para desarrollo local:

- Python 3.12 recomendado.
- Node.js 22 o una versión compatible con Vite 8.
- Redis si se usa `NEORX_INFERENCE_MODE=celery`.
- Para el modo temporal, los pesos `resnet50-res512-all` de TorchXRayVision dentro de `backend/models/`; se descargan una vez si faltan. Para el modo futuro se requerirá un checkpoint compatible, sin renombrar el antiguo para simular el entrenamiento nuevo.

Para el despliegue completo solo se necesita Docker Desktop con Docker Compose v2.

## Inicio local en Windows

### Backend

El entorno virtual guardado previamente puede apuntar a otra instalación de Python. Crea uno nuevo en `.venv`:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Solo para una instalación nueva, genera una clave Fernet y colócala en `backend/.env`. En una instalación existente conserva la clave: cambiarla impediría leer datos cifrados anteriores.

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Para ejecutar sin Redis durante el desarrollo, usa `NEORX_INFERENCE_MODE=thread`. La carga responde sin esperar a la CNN; `inline` queda para pruebas síncronas. Luego:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py createsuperuser
.\.venv\Scripts\python.exe manage.py runserver
```

El backend queda disponible en `http://127.0.0.1:8000/` y Swagger en `http://127.0.0.1:8000/api/schema/swagger/`.

### Frontend

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

La interfaz queda disponible en `http://127.0.0.1:5173/` y usa `http://localhost:8000/api` de forma predeterminada. Para otra URL crea `frontend/.env.local` con:

```text
VITE_API_URL=https://tu-dominio.com/api
```

## Procesamiento asíncrono local

Con Redis activo, cambia `NEORX_INFERENCE_MODE=celery` y ejecuta el worker desde `backend`:

```powershell
.\.venv\Scripts\celery.exe -A neorx worker -l INFO -Q cnn_inference -c 1 --pool=solo
```

En Windows se usa `--pool=solo`. En Linux y Docker el proyecto usa el pool estándar con una sola instancia del modelo para controlar el consumo de memoria.

## Docker

El despliegue local incluye PostgreSQL, Redis, migraciones, Django/Gunicorn,
Celery Worker, Celery Beat y React/Nginx. Conserva datos, imágenes y registros en
volúmenes de Docker. El checkpoint esperado es
`backend/models/neorx_effusion_categories_resnet50.pt`.

En PowerShell, desde la raíz:

```powershell
.\scripts\setup-docker.ps1
docker compose --env-file .env.docker -f docker-compose.prod.yml up -d --build
docker compose --env-file .env.docker -f docker-compose.prod.yml ps -a
```

La interfaz queda en `http://localhost:8080`. Las cuentas demostrativas creadas
por el script son `admin`, `medico` y `recepcionista`; sus contraseñas se guardan
solo en el archivo local e ignorado `.env.docker`.

Comprobación rápida en Windows:

```powershell
curl.exe http://localhost:8080/health/
docker compose --env-file .env.docker -f docker-compose.prod.yml logs --tail 100 backend celery_worker
```

Detener el despliegue sin borrar datos:

```powershell
docker compose --env-file .env.docker -f docker-compose.prod.yml down
```

La configuración HTTPS es opcional y se activa con el perfil `tls` después de
instalar certificados válidos y configurar dominio, CORS, redirección SSL y HSTS.
Consulta [la guía completa de despliegue](DOCKER_DESPLIEGUE.md).

## Verificación

Desde la raíz, sin Docker:

```powershell
.\scripts\preflight-presentacion.ps1
# Si utilizas un entorno virtual, indica su ejecutable absoluto:
.\scripts\preflight-presentacion.ps1 -Python 'C:\ruta\al\entorno\Scripts\python.exe'
```

La prueba `python scripts/smoke_local.py` utiliza el checkpoint real, una base en memoria y un DICOM sintético. Verifica login, carga, inferencia, imagen privada, Grad-CAM, firma, PDF y DICOM SR. No demuestra precisión clínica ni modifica pacientes reales. La verificación completa conserva sus evidencias en `.preflight-temp/`.

Frontend:

```powershell
cd frontend
npm run lint
npm test
npm run build
```

Backend:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

## Estructura

```text
backend/                 Django, DRF, CNN, Celery, informes y entrenamiento
frontend/                React, Vite, Tailwind y visualización clínica
notebooks/               ejecución y entrenamiento en Kaggle
scripts/                 utilidades de despliegue, datos y mantenimiento
nginx/                   proxy inverso y configuración HTTPS
docs/                    auditorías, metodología y estado del proyecto
docker-compose.prod.yml  despliegue integral
```

## Configuración que no se versiona

No deben subirse contraseñas, claves Fernet, tokens, certificados privados, datos clínicos, archivos DICOM ni checkpoints. La configuración real se mantiene en `.env`; el repositorio solo contiene ejemplos.

El estado de cierre y los pendientes externos se mantienen en [docs/estado-cierre-2026-10-12.md](docs/estado-cierre-2026-10-12.md).

## Escaneo temporal en CPU (27/10/2026)

La configuracion local usa `densenet121-res224-all` preentrenada con entrada nativa de 224 px y dos hilos CPU. No utiliza los checkpoints propios. Se conserva la politica `pretrained_effusion_categories`: derrame pleural prioritario y orientacion por categorias con abstencion. Las puntuaciones de modelos distintos no son intercambiables ni prueban precision clinica.

En modo `thread`, el modelo y las dependencias se precargan en el mismo hilo que atiende los escaneos antes de abrir el servidor. Ejecutar un solo backend; para aplicar cambios de `.env`, reiniciarlo. Se puede volver a ResNet con `NEORX_BASELINE_WEIGHTS=resnet50-res512-all` y reinicio. Los mapas de resultados historicos de otro modelo o resolucion requieren un nuevo analisis.

El formulario de informes sincroniza el texto normalizado por el backend al guardar/revisar. La firma envia solo el cambio de estado del contenido revisado y sigue siendo exclusiva del medico; los campos pendientes deben completarse. El PDF definitivo queda disponible despues de firmar.

Verificacion local: 41 pruebas backend, 5 pruebas del formulario, ESLint y compilacion frontend correctos. Prueba de CNN con pixeles sinteticos: DenseNet 0,427-0,940 s frente a ResNet 10,396-18,382 s; son tiempos orientativos de inferencia en esta maquina, no una evaluacion diagnostica ni una garantia de latencia total.

Para comprobar antes de una demostracion que los pesos locales, el
preprocesamiento y la inferencia funcionan sin depender de Internet:

```powershell
cd backend
.\.test-venv312\Scripts\python.exe manage.py verificar_modelo --runs 5 --output ..\qa\modelo_preentrenado\verificacion.json
```

El porcentaje que imprime este comando corresponde exclusivamente a
ejecuciones técnicas válidas. No es `accuracy` clínica. Las métricas clínicas
requieren un conjunto etiquetado independiente y se reportan por clase mediante
sensibilidad, especificidad, precisión, F1 y AUROC.
