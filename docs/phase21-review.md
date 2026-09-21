# Revisión Fase 2.1 — Neo Rayos X

## A. Estado general

**FASE 2.1 TODAVÍA NO CERRADA.**

Las verificaciones de software pasan, pero el proveedor de cifrado instalado no funciona con Django 5.2.14. Desarrollo utiliza actualmente el fallback de campos sin cifrado; producción ahora rechaza ese estado. No equivale a haber implementado cifrado funcional. Antes de cerrar seguridad hay que resolver proveedor, clave consumida, búsqueda/unicidad de CI y migración de datos. Docker tampoco pudo construirse porque su motor no está activo.

No se entrenó ni evaluó la CNN, no se descargaron datasets o pesos, no se creó checkpoint, no se modificó training, no se hizo commit/push ni se alteró staging. Todos los datos y probabilidades de pruebas son sintéticos y verifican software. **Resultado pendiente de ejecución experimental.**

## B. Git inicial

Se ejecutaron status, diff --stat, diff y diff --cached antes de modificar. Había cambios legítimos de fases anteriores; no se revirtieron.

Staged: 9 archivos, 719 inserciones/197 eliminaciones: diagnostico/services.py, diagnostico/views.py, estudios/utils.py, neorx/settings.py, frontend/package-lock.json, App.jsx, api/index.js, AdminUsuariosPage.jsx y DashboardPage.jsx. Había archivos con cambios tanto staged como unstaged. El diff unstaged incluía 31 archivos, 2570 inserciones/831 eliminaciones, entre ellos seis del pipeline training.

Ya eran nuevos: migraciones accounts 0002/0003/0004, migraciones neorx, modelos/auditoría neorx, validators.py, pdf_generator.py, exceptions.py, pytest.ini, documentación CRISP-DM y tres módulos training. Localmente las migraciones previas de accounts, neorx y token_blacklist estaban aplicadas. No se trataron esos archivos nuevos como temporales. El venv existente apunta a Python de otro equipo y falla; se utilizó Python local 3.14.6. Las instrucciones AGENTS.md no aparecieron en el inventario del repositorio.

## C. Archivos modificados en esta revisión

La tabla describe únicamente mis cambios; cada archivo que ya tenía modificaciones conserva el trabajo previo. Los archivos training, estudios/utils.py, niveles, App.jsx y package-lock.json no fueron editados por esta revisión.

| Archivo | Cambio | Motivo |
|---|---|---|
| [README.training.md](C:/u/7mo/taller 1/proyecto/neo/neorx/README.training.md) | Retira tiempos no medidos y aclara estadísticas/integración pendientes. | Evitar resultados experimentales aparentes; conservar instrucciones válidas. |
| [backend/accounts/serializers.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/accounts/serializers.py) | Contraseña write-only, validación Django, hash en creación/edición. | Impedir contraseña predeterminada y edición ignorada. |
| [backend/accounts/views.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/accounts/views.py) | Audita login fallido; comprueba propietario del refresh; reset con hash, correo, expiración y respuesta uniforme. | Eliminar impresión de tokens y reforzar autenticación. |
| [backend/accounts/views_admin.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/accounts/views_admin.py) | PATCH parcial, paginación configurable y desactivación por DELETE. | Corregir actualización y preservar cuentas/auditoría. |
| [backend/conftest.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/conftest.py) | Fixtures compartidas, aislamiento singleton y bloqueo de modelos reales. | Pruebas reproducibles sin pesos ni descargas. |
| [backend/neorx/conftest.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/conftest.py) | Elimina configuración Django manual/plugin anidado. | Desbloquear colección de pytest 9. |
| [backend/diagnostico/results.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/diagnostico/results.py) | Adaptador de resultados estructurados y mapas antiguos. | Mantener contrato de probabilidades en español. |
| [backend/diagnostico/serializers.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/diagnostico/serializers.py) | Normaliza probabilidades para consumidores. | Compatibilidad con registros previos. |
| [backend/diagnostico/tasks.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/diagnostico/tasks.py) | Normaliza persistencia y audita procesamiento. | Evitar guardar estructuras incompatibles con consumidores. |
| [backend/diagnostico/tests.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/diagnostico/tests.py) | Mocks tensoriales, Grad-CAM en módulo real y preprocesamiento aislado. | Actualizar pruebas de software sin checkpoint. |
| [backend/diagnostico/views.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/diagnostico/views.py) | Retira auditoría de cada consulta y oculta errores internos de Grad-CAM. | Auditar eventos relevantes sin exposición de rutas. |
| [backend/estudios/validators.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/estudios/validators.py) | Firmas binarias portables, extensión/contenido, tamaño y decodificación de píxeles DICOM. | Eliminar dependencia nativa de libmagic en Windows/Linux. |
| [backend/estudios/views.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/estudios/views.py) | Recepción carga; umbral configurable; repetición técnica; un despacho Celery; normalización y error seguro. | Permisos y flujo de carga coherente. |
| [backend/estudios/models.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/estudios/models.py) | Producción falla si el proveedor de cifrado no está disponible. | Evitar fallback silencioso a texto plano. |
| [backend/informes/serializers.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/informes/serializers.py) | Estudio de solo lectura, revisión antes de firma e informe firmado inmutable. | Corregir PUT y proteger documentos clínicos. |
| [backend/informes/views.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/informes/views.py) | Escritura médica, generación idempotente, textos preliminares sin anatomía inventada, sello/finalización; corrige SR. | No atribuir diagnóstico definitivo a la IA ni sobrescribir revisión. |
| [backend/informes/pdf_generator.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/informes/pdf_generator.py) | Escapa contenido XML y permite dividir notas largas. | PDF robusto ante texto médico y caracteres especiales. |
| [backend/informes/tests.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/informes/tests.py) | Fixtures válidas y exportaciones reales PDF/SR. | Sustituir comprobación permisiva/WeasyPrint por evidencia real. |
| [backend/neorx/permissions.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/permissions.py) | Permisos de escritura médica, carga por recepción y roles válidos. | RBAC en backend. |
| [backend/neorx/test_phase21.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/test_phase21.py) | 49 regresiones directas de API, seguridad y carga sintética. | Evidencia funcional adicional. |
| [backend/neorx/models.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/models.py) | Auditoría sin request y redacción recursiva de secretos. | El reset/inferencia antes perdía silenciosamente auditoría. |
| [backend/neorx/security.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/security.py) | Redacta parámetros y aclara configuración real del proveedor. | No registrar tokens por URL ni afirmar cifrado inexistente. |
| [backend/neorx/exceptions.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/exceptions.py) | Conserva propiedad error cuando el handler DRF la recibe. | Compatibilidad del frontend con errores estructurados. |
| [backend/neorx/settings.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/settings.py) | CHECK_REVOKE_TOKEN; correo en memoria; valida formato FERNET; PostgreSQL cuando se configura. | Revocación por cambio de contraseña y configuración explícita. |
| [backend/neorx/urls.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/urls.py) | Conecta refresh con vista limitada existente. | Aplicar rate limiting previsto sin rutas duplicadas. |
| [backend/neorx/views_metrics.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/neorx/views_metrics.py) | Fechas validadas, rango limitado, latencia entre timestamps, suma por hora y CNN pendiente. | Evitar errores SQLite y métricas experimentales aparentes. |
| [backend/pacientes/models.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/pacientes/models.py) | Estado requiere_repeticion y rechazo de cifrado ausente en producción. | Representar repetición técnica y no ocultar falta de cifrado. |
| [backend/pacientes/serializers.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/pacientes/serializers.py) | Solo recepción solicita repetición; finalización mediante firma; paciente no reasignable. | Separar estados técnicos y cierre médico. |
| [backend/pacientes/views.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/pacientes/views.py) | Valida roles, audita eliminación y protege cascadas con informes firmados. | Preservar historial clínico y trazabilidad. |
| [backend/pacientes/migrations/0002_estudio_requiere_repeticion.py](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/pacientes/migrations/0002_estudio_requiere_repeticion.py) | AlterField de choices estado; aplicada localmente. | Migración necesaria y explícita; no modifica migraciones históricas. |
| [backend/requirements.txt](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/requirements.txt) | Declara ReportLab, filtros, extensions, Celery, Redis y dependencias de pruebas instaladas. | Dependencias usadas pero ausentes; retira python-magic. |
| [backend/Dockerfile.prod](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/Dockerfile.prod) | Entorno /opt/venv accesible a appuser; libgl1. | Dependencias antes ubicadas bajo /root inaccesible. |
| [backend/.dockerignore](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/.dockerignore) | Excluye entorno, secretos, DB y archivos locales. | Evitar incluir .env en imagen. |
| [docker-compose.prod.yml](C:/u/7mo/taller 1/proyecto/neo/neorx/docker-compose.prod.yml) | Solo proxy publica puertos; beat estándar y clave de cifrado por entorno. | Evitar puertos duplicados y scheduler no instalado. |
| [backend/.env.example](C:/u/7mo/taller 1/proyecto/neo/neorx/backend/.env.example) | Placeholders de clave y contraseña; correo de desarrollo documentado. | No introducir credenciales reales. |
| [frontend/src/api/auth.js](C:/u/7mo/taller 1/proyecto/neo/neorx/frontend/src/api/auth.js) | Logout envía refresh al backend antes de limpiar almacenamiento. | Revocar sesión también en servidor. |
| [frontend/src/context/AuthContext.jsx](C:/u/7mo/taller 1/proyecto/neo/neorx/frontend/src/context/AuthContext.jsx) | Maneja promesa de logout. | Evitar rechazo asíncrono sin manejar. |
| [frontend/src/api/informes.js](C:/u/7mo/taller 1/proyecto/neo/neorx/frontend/src/api/informes.js) | Descarga por /pdf/. | Ruta /descargar/ no existe. |
| [frontend/src/pages/AdminUsuariosPage.jsx](C:/u/7mo/taller 1/proyecto/neo/neorx/frontend/src/pages/AdminUsuariosPage.jsx) | Nombre desde campos JSON; pageSize dispara consulta; contador acepta cero. | Evitar llamada a método Python y paginación inconsistente. |
| [frontend/src/pages/InformePage.jsx](C:/u/7mo/taller 1/proyecto/neo/neorx/frontend/src/pages/InformePage.jsx) | Firma disponible después de revisión. | Coherencia con validación backend. |
| [docs/ml_methodology_review.md](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/ml_methodology_review.md) | Retira instrucción CUDA incompatible no validada. | No presentar compatibilidad Python/CUDA como comprobada. |
| [docs/crisp-dm/2_data_understanding.md](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/crisp-dm/2_data_understanding.md) | Ejemplos con cantidad no medida y declaración de no-resultados. | No confundir dataset publicado con conjunto local adquirido. |

También se crearon este informe, registros phase21-*.txt, JUnit XML, hashes de preservación y un PDF de prueba en docs/evidence. El staging inicial continúa con los mismos 9 archivos y estadísticas.

## D. Problemas encontrados

| ID | Severidad | Problema | Causa | Solución |
|---|---|---|---|---|
| D1 | Alta | Suite no coleccionaba | pytest_plugins anidado y configuración manual | Usa pytest-django y settings del proyecto |
| D2 | Alta | Errores de informes/diagnóstico | Fixtures locales a clases, mocks viejos, PUT requería estudio | Fixtures compartidas, mocks correctos, relación de solo lectura |
| D3 | Crítica | Cualquier usuario podía editar informes | Solo IsAuthenticated | Escritura exclusiva médico, revisión y bloqueo tras firma |
| D4 | Alta | Token reset en stdout y auditoría perdida | print del token y log_audit(None) incompatible | Hash en DB, correo, sin impresión y soporte request ausente |
| D5 | Alta | Contraseña admin ignorada/default compartido | Serializer no tenía password; changeme123 | Campo write-only y set_password; sin default |
| D6 | Alta | PATCH admin devolvía 400 | partial se eliminaba antes de llamar super | Reenvía partial |
| D7 | Alta | Incompatibilidad de resultado CNN | Servicio retornaba estructura y consumidores esperaban mapa | Adaptador compatible; no cambia modelo ResultadoCNN |
| D8 | Alta | Carga frágil/duplicaba tareas | libmagic nativo y dos llamadas delay | Firmas binarias + decodificación; una llamada |
| D9 | Alta | Borradores inventaban normalidad anatómica | Texto estático sin evidencia del modelo | Solo probabilidades disponibles y revisión profesional |
| D10 | Alta | PDF frontend 404 | /descargar/ frente a /pdf/ | Conecta ruta real |
| D11 | Media | Latencia SQLite incorrecta/rangos inválidos | Resta DateTimeField-DateField y int sin validar | Timestamp de creación estudio, fechas y rango validados |
| D12 | Alta | Docker inaccesible/inconsistente | Paquetes bajo /root, puertos duplicados, scheduler ausente | /opt/venv, proxy único, beat estándar; build pendiente |
| D13 | Crítica | Cifrado ausente aunque FERNET existe | django-cryptography importa baseconv eliminado de Django | Rechazo en producción; solución de cifrado pendiente |
| D14 | Media | Documentación aparentaba tiempos/dataset local | Estimaciones y ejemplos numéricos sin ejecución | Retira tiempos y aclara cantidades/ejemplos pendientes |

## E. Tests

Comando: `python -m pytest -v --junitxml=../docs/phase21-junit.xml`, desde backend. La primera colección dio un error de infraestructura. Tras corregirla: **20 passed, 5 failed, 5 errors**. Resultado final:

| Módulo | Passed | Failed | Errors | Skipped |
|---|---|---|---|---|
| diagnostico | 12 | 0 | 0 | 0 |
| informes | 9 | 0 | 0 | 0 |
| neorx | 49 | 0 | 0 | 0 |
| pacientes | 9 | 0 | 0 | 0 |
| TOTAL | 79 | 0 | 0 | 0 |

Pacientes mantiene 9/9; informes 9/9; diagnóstico 12/12. La suite impide cargar/descargar ResNet real. No se borraron pruebas ni se usaron skips. Ningún test actual necesita realmente un checkpoint: los servicios y Grad-CAM son pruebas unitarias con mocks. La integración con pesos reales continúa pendiente y no cuenta como prueba clínica.

Django check: 0 problemas. Verificación directa adicional del handler: HTTP 500 genérico sin detalle interno (phase21-error-handler.txt). makemigrations --check --dry-run: No changes detected. Se creó solamente pacientes.0002, por Estudio.estado y la opción requiere_repeticion ausente; aplicada localmente OK y también en DB de pruebas. No se modificaron migraciones históricas.

### Clasificación individual de los fallos iniciales

| Test / módulo | Excepción | Causa, fixture y modelo | Categoría | Solución |
|---|---|---|---|---|
| Colección neorx | Failed: pytest_plugins no top-level | neorx/conftest.py | A/G infraestructura/configuración | Retira configuración anidada |
| diagnostico.TestResultadoCNNModel.test_crear_resultado_cnn | fixture not found | imagen_dicom ausente; ResultadoCNN | B fixture | Fixture compartida |
| informes.TestInformePreliminarModel.test_crear_informe | fixture not found | imagen_con_resultado solo existía en TestInformeAPI; InformePreliminar | B fixture | Fixture compartida |
| informes.TestExportPDF.test_descargar_pdf_firmado | fixture not found | auth_client/imagen_con_resultado fuera de alcance; además mock HTML viejo | B/F fixture/test viejo | Compartidas y PDF real |
| informes.TestExportDICOMSR.test_descargar_dicom_sr_firmado | fixture not found; luego AssertionError 501 != 200 | Compartidas ausentes; import VerificationSOPClass inexistente | B/E fixture/lógica | Fixtures válidas y retira import inválido |
| informes.TestExportDICOMSR.test_descargar_dicom_sr_no_firmado | fixture not found; luego AssertionError 501 != 400 | Misma fixture/import ocultaba validación de estado | B/E | Fixtures e import corregidos |
| diagnostico.TestDetectorTorax.test_predecir_desde_png | TypeError: expected np.ndarray, got MagicMock | Mock singleton contaminaba transform; salida no tensorial y contrato viejo | B/F | Aislamiento, tensor y contrato estructurado |
| diagnostico.TestDiagnosticoAPI.test_gradcam_view | AttributeError: diagnostico.views sin GeneradorGradCAM | Clase importada dentro de get; archivo ficticio no legible | B/F | Patch en diagnostico.gradcam; lector/preprocesamiento mock |
| informes.TestInformeAPI.test_generar_informe_sin_cnn | AssertionError | Fixture sin imagen produce mensaje de imagen, no de CNN | F test viejo | Espera mensaje correspondiente al caso real |
| informes.TestInformeAPI.test_actualizar_informe | AssertionError: 400 != 200 | PUT requería estudio; InformePreliminar | E lógica | Relación de solo lectura |
| informes.TestInformeAPI.test_firmar_informe_como_medico | AssertionError: 400 != 200 | PUT parcial requería estudio; fixture saltaba revisión | E/F | Campo protegido y fixture revisada |
| neorx.test_admin_user_crud_password_soft_delete (nuevo) | AssertionError: 400 != 200 | Vista admin perdía partial | E | PATCH corregido |
| neorx.test_critical_lists_authenticated[/api/pacientes/] (nuevo) | AssertionError: 200 != 401 | api_client era la misma instancia autenticada de auth_medico | B | Cliente anónimo independiente |
| neorx.test_critical_lists_authenticated[/api/pacientes/estudios/] (nuevo) | AssertionError: 200 != 401 | Misma instancia de fixture | B | Cliente anónimo independiente |
| neorx.test_critical_lists_authenticated[/api/estudios/imagenes/] (nuevo) | AssertionError: 200 != 401 | Misma instancia de fixture | B | Cliente anónimo independiente |
| neorx.test_critical_lists_authenticated[/api/informes/] (nuevo) | AssertionError: 200 != 401 | Misma instancia de fixture | B | Cliente anónimo independiente |
| neorx.test_critical_lists_authenticated[/api/metrics/operacionales/] (nuevo) | AssertionError: 200 != 401 | Misma instancia de fixture | B | Cliente anónimo independiente |

resultado_cnn es la relación inversa **OneToOne** de ResultadoCNN.imagen hacia ImagenDICOM. ResultadoCNN.patologias es JSONField. No se cambió ese modelo para acomodar fixtures.

## F. Pendientes

No quedan FAIL/ERROR en la suite final.

| Test / comprobación | Excepción | Causa | Categoría | Bloqueante | Acción futura |
|---|---|---|---|---|---|
| Import proveedor cifrado, fuera de suite | ImportError: baseconv de django.utils | Dependencia incompatible con Django actual | D | Sí, seguridad | Proveedor compatible y estrategia de datos/búsqueda; probar cifrado real |
| Build Docker, fuera de suite | Motor npipe dockerDesktopLinuxEngine no encontrado | Docker Desktop detenido/no disponible | A/D | Para validar despliegue | Activar motor y construir localmente |
| Integración con checkpoint real, no ejecutada | No ejecutada | Fase 3 no autorizada | C | Para afirmar CNN validada | Ejecutar posteriormente con pesos y datos reales |
| Navegación frontend integral, no ejecutada | No ejecutada | Se verificó build y contrato/API, no navegador completo | H | Para cierre integral de UX | Recorrer flujo con roles y datos de prueba |
| Conformidad SR/TID, fuera de suite | No evaluada completamente | Lectura estructural no acredita IOD/TID/códigos | H | Para afirmar conformidad | Validador independiente y revisión con datos/equipo real |

## G. P1–P13

El adjunto no define un catálogo oficial P1–P13 y no se encontró uno en documentos inspeccionados. Esta numeración de trabajo permite trazabilidad, sin afirmar correspondencia con un catálogo anterior.

| ID | Área | Estado | Evidencia |
|---|---|---|---|
| P1 | Infraestructura pytest/Django | RESUELTO | Colección completa; check correcto |
| P2 | Informes y fixtures | RESUELTO | 9/9 informes |
| P3 | JWT/logout/revocación | RESUELTO | Login 200, reutilización refresh 401, revocación masiva refresh |
| P4 | Password reset | RESUELTO | Hash, caducidad, respuesta uniforme, uso único, access anterior 401 |
| P5 | Roles/RBAC | RESUELTO | Médico escribe informes; otros 403; recepción carga; usuarios solo admin |
| P6 | Administración usuarios | RESUELTO | CRUD, filtros, hash, PATCH, activación y DELETE lógico |
| P7 | Pacientes | RESUELTO | 9/9, historial protegido y auditoría |
| P8 | Estudios/repetición | RESUELTO | Migración aplicada y carga borrosa persiste repetición |
| P9 | Archivos/MIME | RESUELTO | PNG/DICOM sintéticos, vacíos, corruptos, extensión falsa y exceso tamaño |
| P10 | PDF/SR | PARCIAL | PDF real válido; SR parseable, conformidad pendiente |
| P11 | Endpoints | RESUELTO | Informes e imágenes 200 autenticado/401 anónimo |
| P12 | Dashboard | RESUELTO | SQLite con datos, sin datos, rango vacío y entradas inválidas |
| P13 | Auditoría/seguridad final | PARCIAL | Eventos y redacción probados; cifrado real pendiente |

## H. Endpoints críticos

Resultados obtenidos con APIClient contra Django y DB de prueba, sin servidor externo:

| Endpoint | Resultado real |
|---|---|
| POST /api/token/ | 200 válido, 401 inválido; audita ambos |
| POST /api/token/logout/ | 200; refresh revocado rechaza reutilización 401; ajeno 400 |
| POST /api/token/revoke/ | 200; ambos refresh de prueba rechazados 401 |
| /api/admin/users/ | 201 crear, 200 listar/editar/reset/activar, 204 desactivar; otros roles 403 |
| /api/pacientes/ | 200 autenticado, 401 anónimo; suite CRUD/búsqueda pasa |
| /api/pacientes/estudios/ | 201 crear, 200 listar/filtrar, 401 anónimo |
| /api/estudios/imagenes/ | 200 autenticado, 401 anónimo |
| POST /api/estudios/upload/ | PNG/DICOM borrosos 200 con alerta; inválidos 400; roles ajenos 403; despacho mock 202 |
| /api/informes/ | Lista/detalle 200, inexistente 404, escritura no médica 403 |
| /api/informes/generar/ | 200 borrador; sin imagen 400; no sobrescribe edición existente |
| /api/informes/<id>/pdf/ | 200, application/pdf, bytes PDF reales; exige firma y médico/fecha |
| /api/metrics/operacionales/ | 200 SQLite, entradas inválidas 400; CNN pendiente |

## I. Seguridad

JWT usa SimpleJWT, rotación y blacklist. Todas las migraciones blacklist están aplicadas. Logout y revoke revocan refresh; **el access de una sesión cerrada continúa válido hasta su expiración de 30 minutos**. No se afirma revocación inmediata de access por logout. Un cambio de contraseña invalida access por CHECK_REVOKE_TOKEN; reset además blacklista refresh.

RBAC se verifica en backend mediante requests manipuladas, sin confiar en frontend. Password reset almacena hash SHA-256 de token aleatorio de 64 caracteres, caduca en una hora, valida contraseña Django y evita distinguir cuenta existente/inexistente en estado/cuerpo; no se midió equivalencia de tiempos.

Correo por defecto usa locmem: conserva mensajes solo durante el proceso, no entrega correo externo ni imprime tokens. Hay que configurar correo real antes de uso operativo, sin introducir credenciales en Git. Usuarios admin usan passwords write-only y hashes; flags is_staff/is_superuser no están expuestos para escalamiento.

AuditLog existente registra login/fracaso/logout/revoke/reset, usuarios, pacientes/estudios, carga/calidad/repetición e informes/PDF; procesamiento asíncrono probado con mock. Redacta nombres de claves sensibles, incluso anidadas. No se agregó sistema paralelo ni auditoría de cada GET de resultados.

.env está ignorado y no aparece entre archivos versionados; ejemplos contienen placeholders. FERNET local existe y su formato pasa validación, pero **no hay cifrado activo**. El proveedor instalado usa CRYPTOGRAPHY_KEY/SECRET_KEY, no FERNET_KEYS; requiere resolución explícita. Los archivos de imagen en almacenamiento y su entrega HTTP necesitan revisión de protección antes de despliegue clínico: cifrar un FileField no acredita cifrado del contenido binario.

## J. PDF

Motor real: ReportLab 5.0.1, declarado en requirements. Se generó por endpoint firmado un archivo mayor de 1000 bytes que empieza por %PDF, con Content-Type application/pdf. pypdf extrajo datos del paciente, hallazgos y advertencia “No sustituye”. Archivo sintético: docs/evidence/synthetic-report.pdf. Se conserva fallback xhtml2pdf existente; la prueba pasó por ReportLab sin sustituir el motor por mock. No se acredita firma digital criptográfica: es firma registrada en el flujo del sistema.

## K. DICOM

La carga valida firmas y decodifica el pixel_array antes de persistir. DICOM sin preámbulo solo se acepta si estructura y decodificación pasan. No se confía en extensión o MIME declarado por navegador. Un PNG válido con MIME declarado text/plain pasa porque su contenido real sí es PNG; extensiones falsas y contenido corrupto se rechazan. No se utiliza libmagic/python-magic-bin.

Metadata de DX y dimensiones verificadas en DICOM sintético. Calidad técnica usa varianza de Laplaciano y umbral configurable, conserva valor por defecto 100; no se redujo para hacer pasar tests. La imagen borrosa persiste calidad, alerta y requiere_repeticion; no es diagnóstico médico. PNG convertido DICOM fue generado y persistido en la prueba.

SR utiliza pydicom, BasicTextSRStorage, UID SOP coherente entre dataset/meta, raíz CONTAINER y ContentSequence. Lectura estructural pasa. IOD, códigos, relación con estudio/equipo y conformidad TID siguen pendientes; no se afirma conformidad normativa por extensión .dcm.

## L. Frontend

npm run build: exit 0, Vite 8.0.16, 2809 módulos, compilado en 2.94 s. JavaScript 930.80 kB (gzip 268.96 kB); permanece advertencia de chunk >500 kB. Se corrigieron logout, nombres/paginación de usuarios, ruta PDF y requisito de revisión antes de firma. Sin rediseño ni páginas duplicadas. Build no sustituye prueba integral en navegador.

## M. Docker

**PARCIALMENTE VERIFICADO**: inspección y correcciones locales de Dockerfile, compose y dependencias. docker version falló al conectar con el motor Linux; no hubo build exitoso ni despliegue. Configuración ahora toma PostgreSQL solo si POSTGRES_HOST está presente; desarrollo sigue SQLite. No se declara producción lista, especialmente por cifrado pendiente.

## N. Documentación

No apareció README.md en la raíz. README.training.md y docs se inspeccionaron como UTF-8; no se detectaron fragmentos sin sentido ni caracteres corruptos en los Markdown revisados. Se corrigieron únicamente tiempos no medidos, ejemplos aparentando cantidades locales y una instrucción CUDA/Python no sustentada. La documentación histórica del pipeline conserva su contenido válido. El log inicial tuvo pérdida de codificación en la captura extensa; se conserva un resumen fiel ASCII de sus resultados, sin reconstruir texto perdido.

## O. Preparación para Fase 3

**No se recomienda iniciar todavía Fase 3** hasta resolver cifrado y terminar verificaciones operativas indicadas. El pipeline existente permanece preparado como trabajo previo; no se ejecutó ni se certificó su comportamiento experimental en esta revisión. Los 12 archivos training inspeccionados por hash permanecen idénticos byte a byte. Tiempos clínicos, AUC, sensibilidad, especificidad, F1 y reducción de tiempos: **Resultado pendiente de ejecución experimental.**

Evidencias: phase21-tests.txt, phase21-junit.xml, phase21-django-check.txt, phase21-migration.txt, phase21-frontend-build.txt, phase21-training-hashes.json, phase21-training-verification.txt, phase21-git-final-status.txt, phase21-git-final-stat.txt y PDF sintético. Los diffs de whitespace conservan observaciones del trabajo previo, especialmente training, que no se corrigió por restricción expresa.
