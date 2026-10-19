# Estado de cierre de Neo RX

**Corte técnico:** 12 de octubre de 2026  
**Objetivo:** distinguir el avance comprobado del cronograma histórico y concentrar el cierre en tareas reales.

## Estado verificado

| Área | Estado | Evidencia actual |
|---|---|---|
| Configuración, Django y base de datos | Completa | `manage.py check` sin errores y sin migraciones pendientes. |
| Autenticación y roles | Completa | JWT, renovación, recordar sesión, revocación, permisos y recuperación por código. |
| Pacientes y usuarios | Completa | CRUD, búsqueda, filtros, paginación y edición administrativa. |
| Estudios radiológicos | Completa | Carga DICOM/PNG/JPEG, estudio torácico y archivo de radiografías no torácicas. |
| Procesamiento asíncrono | Completa | Redis, Celery, cola de inferencia, estado y polling. |
| CNN | Integrada | Checkpoint local, singleton, 12 hallazgos, umbrales y salida ordenada. |
| Grad-CAM | Integrado | Mapa de calor calculado bajo demanda y presentado en el visor. |
| Informes | Completa | Plantilla clínica, edición, estados, firma médica, PDF y DICOM SR. |
| Métricas y administración | Completa | Tableros por rol, actividad, usuarios, auditoría y configuración. |
| Seguridad de aplicación | Avanzada | CI cifrado, búsqueda HMAC, medios privados, headers y registro estructurado. |
| Pruebas | Completa para el alcance actual | Suite backend completa, pruebas frontend, contraste, lint y compilación aprobados. |
| API y despliegue | Completa técnicamente | OpenAPI/Swagger/ReDoc y stack Docker probado de extremo a extremo. |
| Entrenamiento | Completa técnicamente | Notebook Kaggle, fine-tuning, checkpoint y documentación reproducible. |

El cronograma original conserva valor como planificación histórica, pero sus porcentajes de septiembre ya no representan el código actual.

## Pendientes necesarios antes de producción real

Estos puntos no se resuelven únicamente escribiendo código y requieren decisiones, infraestructura o validación externa:

1. **Validación clínica independiente.** Medir AUC, sensibilidad, especificidad, calibración y errores por patología con un conjunto ajeno al entrenamiento y con revisión profesional. El resultado de Kaggle no equivale a aprobación clínica.
2. **Correo de producción.** Configurar una cuenta SMTP autorizada, contraseña de aplicación, remitente y prueba real de entrega de los códigos de recuperación. El modo local usa correo en memoria.
3. **Servidor y dominio.** Definir host, DNS, certificados TLS válidos, secretos, capacidad de CPU/RAM y responsables de operación.
4. **Respaldo y restauración.** Programar copias cifradas de PostgreSQL y medios, aplicar retención y demostrar una restauración en un entorno aislado.
5. **Privacidad operacional.** Aprobar perfiles de acceso, consentimiento, política de conservación y procedimiento de incidentes de acuerdo con la normativa aplicable.
6. **Validación DICOM institucional.** Probar archivos de los equipos reales de la clínica y validar interoperabilidad del DICOM SR con el PACS/RIS de destino.
7. **Prueba de aceptación.** Ejecutar un recorrido con administrador, recepción y médico usando datos sintéticos; registrar incidencias y la aprobación del responsable.

## Cierre técnico inmediato

- Rehacer el entorno virtual local con Python 3.12; el directorio `backend/venv` existente conserva referencias a otra instalación de Python.
- Mantener el checkpoint fuera de Git y confirmar `NEORX_MODEL_PATH` en cada ambiente.
- Sustituir los certificados de desarrollo por certificados válidos antes de exponer el sistema.
- Definir valores reales en `.env`; no reutilizar los valores del archivo de ejemplo.
- Ejecutar la lista de pruebas del README en el commit destinado a la entrega.
- Crear un tag semántico solo después de la prueba de aceptación y conservar las notas de versión.

## Criterio de finalización

Neo RX puede considerarse terminado para presentación académica cuando la demostración de los tres roles, el flujo DICOM, la inferencia, el mapa de calor, el informe firmado y la descarga PDF se ejecuten con datos sintéticos sin errores. Puede considerarse apto para un piloto controlado únicamente después de completar los siete pendientes externos anteriores.
