# Fase 2.2 — Cifrado y cierre técnico de Neo Rayos X

## A. Cifrado anterior

Se pretendía proteger `Paciente.ci` y `ImagenDICOM.archivo_dicom` con `encrypt(...)` de django-cryptography. El segundo campo sólo representaba la ruta del archivo; nunca cifró sus bytes. En este entorno el import fallaba y el fallback de desarrollo dejaba ambos campos sin cifrado. Fase 2.1 había impedido ese fallback en producción, pero seguía sin existir un proveedor compatible.

La base local tenía 2 pacientes y 24 estudios. Sus CI eran texto plano antes de esta migración. Nombres, apellidos, fecha de nacimiento, teléfono, observaciones, contenido de informes, rutas, imágenes y metadata original tampoco estaban cifrados. No se afirma que toda la base esté cifrada ahora: esta fase protege el CI y restringe la entrega HTTP de los archivos.

## B. Problema django-cryptography

La distribución instalada es django-cryptography 1.1. Su archivo `django_cryptography/core/signing.py` importa `baseconv` desde `django.utils`, API retirada e inexistente en Django 5.2.14. De ahí el `ImportError`; no era una clave Fernet incorrecta.

Su configuración `CRYPTOGRAPHY_KEY`, o en su ausencia `SECRET_KEY`, alimentaba su derivación de clave. La variable del proyecto `FERNET_KEY` y la lista `FERNET_KEYS` no eran consumidas por ese proveedor. Tenerlas configuradas no acreditaba cifrado. Se retiraron la dependencia de requirements, la aplicación de settings y los imports incompatibles. No se modificó site-packages ni se reescribieron migraciones históricas.

## C. Solución implementada

`cryptography==50.0.1`, ya disponible en el entorno, proporciona Fernet autenticado. El campo propio únicamente adapta esas primitivas a Django: escritura cifrada aleatoria, lectura autenticada y almacenamiento TEXT con prefijo versionado `neorx$1$`. No implementa AES ni otro algoritmo manualmente. [Documentación oficial de Fernet](https://cryptography.io/en/latest/fernet/).

`FERNET_KEY` se lee del entorno; el .env local continúa ignorado por Git y excluido del contexto Docker. Es obligatoria y se valida tanto en desarrollo como en producción. Clave incorrecta, token alterado o texto plano almacenado provocan una excepción; no se devuelve silenciosamente el dato original. No se cambió ni se imprimió la clave existente.

Antes de elegir el índice se revisaron los filtros por CI, SearchFilter, admin y el ordenamiento existente. `ci_search_hash` es un HMAC-SHA256 único del CI normalizado: Unicode NFKC, mayúsculas y eliminación de espacios. Su clave de 32 bytes se deriva de la clave Fernet mediante HKDF-SHA256 con contexto exclusivo `neorx:ci-search-index:v1`; no es un hash simple del identificador. [Documentación oficial de HKDF](https://cryptography.io/en/latest/hazmat/primitives/key-derivation-functions/#hkdf).

La API oculta este índice. La validación del serializer detecta duplicados y la restricción UNIQUE en DB protege la unicidad incluso entre escrituras concurrentes. `save()` y `bulk_create()` mantienen el índice; actualizar CI mediante QuerySet.update/bulk_update o expresiones se rechaza para evitar desincronizarlo.

Búsqueda exacta/iexact usa HMAC. La búsqueda parcial existente descifra únicamente la columna CI en memoria, calcula coincidencias y filtra por los índices, sin índice de subcadenas en claro. El ordenamiento por CI de la API también se resuelve en memoria y envía sólo IDs/rangos a SQL. Ambas operaciones cuestan un recorrido de los pacientes candidatos; esta solución mantiene la funcionalidad actual, pero requiere revisar rendimiento antes de escalar. No se ofrece búsqueda cifrada genérica para cualquier lookup ORM.

Los nuevos eventos de auditoría redactan CI, nombres de archivo y secretos. Una migración redacta copias históricas de CI/nombres de archivo. El middleware no registra valores de consultas ni rutas concretas de media; Nginx deja de incluir URLs, consultas y referers en su access log. Los logs antiguos no se reescribieron ni se certificó que carezcan de datos personales históricos.

## D. Migraciones

Antes de editar modelos: `python manage.py makemigrations --check --dry-run` → **No changes detected**.

| Migración nueva | Finalidad | Estado local |
|---|---|---|
| pacientes.0003_encrypt_ci | Añadir índice HMAC, ampliar almacenamiento CI, convertir datos, aplicar unicidad | Aplicada OK |
| neorx.0003_redact_audit_identifiers | Redactar CI y filenames en payloads de auditoría | Aplicada OK |

La primera migra todos los datos en una transacción y cancela ante formatos incompatibles o duplicados normalizados. Tiene operación inversa que recupera el CI original antes de restaurar el esquema anterior; la prueba MigrationExecutor demuestra ida y vuelta conservando paciente/estudio. La segunda conserva eventos, IDs y relaciones; su reverso es noop y **no restaura** las copias redactadas por motivos de privacidad.

El procedimiento local [phase22-migrate-local.py](evidence/phase22-migrate-local.py) exige aplicación detenida y base SQLite sin la migración aplicada. Preparó un backup cifrado de toda la base en `backend/.backups/phase22-pre-encryption.sqlite3.fernet`, verificó su descifrado y lo excluyó de Git y Docker. Conservó **2/2 pacientes y 24/24 estudios**, sus IDs y relaciones; comprobó todos los CI e índices, integridad SQLite `ok` y ejecutó VACUUM para retirar páginas obsoletas de la base activa. [Evidencia agregada](evidence/phase22-local-migration.json).

En Windows hubo un intento inicial de backup que se detuvo antes de migrar porque el context manager SQLite no cerraba el archivo. Se corrigió usando cierre explícito, se comparó semánticamente el snapshot cifrado con la base y se retiraron únicamente los temporales propios. La ejecución definitiva terminó con código 0. La copia cifrada queda disponible para recuperación; conservar la clave fuera del repositorio es indispensable. Revertir el CI deja texto plano y exige detener la aplicación y usar código compatible con el esquema anterior. No hacerlo como operación ordinaria de producción.

## E. Evidencia criptográfica

| Prueba | Resultado |
|---|---|
| Lectura ORM y recuperación del valor lógico | PASS |
| SELECT SQL directo: CI distinto del original, token versionado | PASS |
| Misma entrada produce ciphertexts diferentes | PASS |
| Clave incorrecta rechazada | PASS |
| Token corrupto o texto plano almacenado rechazado | PASS |
| Búsqueda exacta/normalizada, parcial y unicidad | PASS |
| Edición, bulk_create y ordenamiento lógico por CI | PASS |
| Sin clave en DEBUG=True y False: no se escribe texto plano | PASS |
| DEBUG=False con clave válida: roundtrip cifrado | PASS |
| Clave y CI sintético ausentes del logging capturado; CI de auditoría redactado | PASS |
| Datos locales existentes: 2/2 CI físicos cifrados y recuperables | VERIFICADO |

La prueba física usa cursor SQL, independiente del descifrado automático del ORM. Comprueba desigualdad respecto al original y ausencia del CI sintético dentro del token. La migración local compara en memoria cada valor original con su descifrado y con el valor físico almacenado, sin publicar identificadores, tokens reales ni claves. Esto acredita la **columna CI**, no la ausencia global de cualquier identificador en todos los campos clínicos o en archivos.

## F. Tests

Comando solicitado, desde backend: `python -m pytest -v`. Se agregó `--junitxml=../docs/phase22-tests.xml` para conservar evidencia. No se eliminaron pruebas ni se añadió skip.

| Módulo | Passed | Failed | Errors | Skipped |
|---|---:|---:|---:|---:|
| Pacientes (anteriores) | 9 | 0 | 0 | 0 |
| Diagnóstico (anteriores) | 12 | 0 | 0 | 0 |
| Informes (anteriores) | 9 | 0 | 0 | 0 |
| NeoRX/Fase 2.1 (anteriores) | 49 | 0 | 0 | 0 |
| Cifrado/media/ordenamiento (nuevos) | 18 | 0 | 0 | 0 |
| **TOTAL** | **97** | **0** | **0** | **0** |

[Salida pytest](phase22-tests.txt), [JUnit](phase22-tests.xml), [resumen e integridad](evidence/phase22-integrity.json).

Una invocación intermedia desde la raíz no cargó pytest.ini de backend y produjo un error de colección por settings sin configurar. Se corrigió ejecutando desde backend; ese error de invocación no se ocultó mediante skip ni cambios de pruebas.

## G. Regresiones

**Los 79 tests anteriores siguen pasando**, junto a 18 nuevos. Django check: **0 problemas**. Makemigrations check/dry-run final: **No changes detected**. [Django](phase22-django-check.txt), [coherencia de migraciones](phase22-migration-check.txt).

`npm run build` terminó con código 0. Mantiene la advertencia de bundle grande; no es fallo del build. Los únicos cambios frontend responden a la protección de media: los dos visores existentes obtienen imágenes mediante Axios con JWT y muestran Blob URLs, revocándolas al desmontar. No hubo rediseño. El hook rechaza enviar el token a un origen externo. [Build](phase22-frontend-build.txt).

Git status/diff se capturaron antes y después. El diff staged existente se comparó byte a byte y está intacto. Los **12 archivos de backend/training/** comparados conservan sus hashes SHA-256; no se ejecutaron scripts de entrenamiento, cargas reales de pesos ni descargas de datasets. Sus cambios preexistentes permanecen intactos. No hubo commit, push, reset, restore masivo ni rebase. El diff --check global detecta whitespace preexistente, incluido training, que no se corrigió para preservar ese trabajo.

## H. Docker — NO VERIFICABLE

`docker version` encuentra cliente 29.8.0, pero falla la conexión con `dockerDesktopLinuxEngine` y termina con código 1. [Salida exacta](phase22-docker.txt).

**Docker no verificable en el entorno actual: motor no disponible.**

No se ejecutó build de producción. La inspección estática encuentra gunicorn y ReportLab en requirements, OpenCV headless y librerías runtime en Dockerfile.prod, USER appuser y exclusiones .env/db/media/logs/backups en backend/.dockerignore. Esto no acredita instalación, arranque ni permisos no-root efectivos. Las variables de entorno del compose no se incorporaron como claves en código o instrucciones COPY.

Se corrigió el bloque preexistente inválido `proxy_params {}` expandiendo sus directivas donde se utilizaban, y se respetó la referencia al upstream nombrado backend en el proxy principal. Las pruebas de configuración verifican el proxy privado y ausencia de alias público; **no sustituyen nginx -t**. Build, validación Nginx, TLS y permisos de volúmenes siguen pendientes en un motor disponible. **Producción no se declara lista.**

## I. DICOM

La revisión local del FileField encuentra **24 originales presentes: 1 DICOM, 7 PNG y 16 JPEG**, formatos admitidos por el flujo actual. El DICOM se pudo parsear y no contiene valores en PatientName, PatientID, PatientBirthDate, AccessionNumber ni ReferringPhysicianName. [Evidencia sin identificadores](evidence/phase22-dicom.json). Esa observación de un archivo no garantiza anonimización de nuevas cargas ni ausencia de identificadores incrustados en píxeles u otros tags.

| Elemento | Protección real |
|---|---|
| CI en DB | Fernet autenticado + índice HMAC |
| Ruta FileField | Texto plano interno; no equivale a cifrado del binario |
| DICOM/PNG/JPEG y su metadata original | Bytes sin cifrar; no hay eliminación general de tags al subir |
| Acceso HTTP a media | JWT y rol clínico activo; sólo archivos registrados; traversal rechazado; cache private/no-store |
| Acceso directo al disco/volumen | Depende de permisos del entorno; el JWT no lo protege |

Django ya no sirve media con static() público. Ambos Nginx envían `/media/` al backend con Authorization, usando `^~` para que una extensión PNG/JPEG no salte al bloque público de estáticos. En pruebas, anónimo recibe 401, médico autorizado accede, usuario inactivo no accede y archivos no registrados devuelven 404. Los roles admitidos mantienen el RBAC clínico existente: médico, recepción y administrador.

Estrategia separada para almacenamiento clínico: volumen/disco y backups cifrados con gestión de claves y permisos, y, si se necesita cifrado a nivel de archivo, storage autenticado con claves por objeto, lectura compatible con conversión/CNN/PDF y recuperación probada. No se implementó ese rediseño en esta fase ni se atribuyó cifrado binario a FileField.

DICOM SR permanece **estructuralmente parseable; conformidad normativa completa pendiente**. No se amplió SR ni se afirmó conformidad TID/IOD sin validador independiente.

## J. Seguridad pendiente

1. Docker de producción: build real, instalación de dependencias, gunicorn/ReportLab/OpenCV, arranque no-root, permisos de volúmenes, nginx -t y TLS.
2. Almacenamiento clínico en reposo: archivos y otros datos personales de DB siguen sin cifrado de aplicación; aplicar la estrategia de volumen/backups y decidir cifrado adicional según uso real.
3. Custodia y recuperación de FERNET_KEY, retención de backups y procedimiento de rotación: una nueva clave necesita recifrar CI y regenerar los HMAC de forma coordinada. No basta sustituir .env.
4. Revisar acceso/retención de logs históricos, que podrían contener identificadores anteriores a esta redacción; no se borraron evidencias ni logs del usuario.
5. Correo real de producción: configurar SMTP o proveedor equivalente. El entorno comprobado usa `django.core.mail.backends.locmem.EmailBackend`; no se introdujeron credenciales ni se enviaron mensajes externos.
6. Conformidad normativa completa DICOM SR mediante validador independiente.

## K. Estado final

**FASE 2 CERRADA TÉCNICAMENTE — LISTA PARA FASE 3**

El bloqueo del CI quedó resuelto con cifrado real, migración aplicada sin perder pacientes/estudios, búsqueda/unicidad conservadas, acceso privado a archivos y 97 pruebas aprobadas. El cierre corresponde al alcance de software de esta fase; los pendientes operativos y clínicos anteriores impiden declarar producción lista. Docker no disponible no se presenta como fallo de código.

**No se inició Fase 3.** Dataset, entrenamiento y evaluación experimental requieren autorización posterior.

## Archivos de esta fase

Modificados: `.gitignore`, `backend/.dockerignore`, `backend/requirements.txt`, `backend/estudios/models.py`, `backend/neorx/{models,security,settings,urls}.py`, `backend/pacientes/{models,serializers,views}.py`, `frontend/src/pages/InformePage.jsx`, `frontend/src/components/scan/VisorImagen.jsx`, `nginx/nginx.conf`, `nginx/conf.d/default.conf`.

Nuevos: `backend/neorx/encryption.py`, `backend/neorx/fields.py`, `backend/neorx/test_encryption.py`, `backend/pacientes/filters.py`, `backend/estudios/media.py`, las dos migraciones descritas, `frontend/src/hooks/usePrivateImage.js` y los documentos/evidencias phase22. La base SQLite y el backup cifrado son locales e ignorados. El resto del diff pertenece al estado previo: no se atribuye a esta fase.
