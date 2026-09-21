# Mejoras del frontend — paquete aprobado

Implementado el 18/09/2026 usando taste-skill, impeccable y emil-design-eng. Dirección clínica sobria: azul marino y celeste, tipografía existente, superficies blancas, controles de 44 px y animación discreta.

| Antes (Before) | Después (After) | Motivo (Why) |
|---|---|---|
| Clases de botones y campos sin definición | Estilos compartidos, foco visible y estados coherentes | Formularios legibles y consistentes |
| Menú expandido solo por hover, superpuesto al contenido | Navegación fija en escritorio y menú móvil con Escape, foco e inert | Acceso con mouse, teclado y pantalla pequeña |
| Conteos calculados desde una página de resultados | Conteos agregados de toda la base, respetando fechas de registro | No confundir datos paginados ni valores cero |
| Tablero único | Médico/recepción centrados en pacientes; administrador con pestañas clínica y administración | Prioridades y permisos de cada rol |
| Pacientes con búsqueda básica | Nombre/CI, género, fechas, orden y 10/20/50 por página, persistidos en URL | Encontrar registros y regresar a la consulta |
| Estudios redirigía a escaneo | Lista real, filtros, detalle e informe para el médico | Consultar sin iniciar una carga |
| Sin cola de trabajo | Informes sin firmar, procesamiento, errores y repetición técnica | Seguimiento de tareas pendientes |
| Auditoría sin pantalla | Historial paginado y filtrable | Administrador ve actividad global; otros roles solo la propia |
| Errores de hooks, búsquedas atrasadas y previews acumulados | Hooks incondicionales, cancelación/descartado de respuestas viejas, liberación de Blob URLs | Evitar fallos y consumo innecesario |
| Carga conjunta de todas las páginas | Importación por ruta | Compilación sin advertencia de chunks grandes |
| Texto afirmaba entrenamiento de 112.000 radiografías | Texto acorde al análisis experimental y la revisión médica | Evitar afirmar entrenamiento no realizado |

## Pantallas y permisos

- `/dashboard`: clínica para los tres roles; administración disponible solo al administrador.
- `/pacientes`: CRUD existente mejorado; vínculo a estudios del paciente.
- `/estudios`: lista y detalle; abrir informe disponible al médico cuando existe.
- `/pendientes`: cuatro colas, con filtros en servidor.
- `/actividad`: historial global para administrador y propio para médico/recepcionista. API exclusivamente de lectura, sin snapshots, CI, metadata, IP ni credenciales.
- `/admin/usuarios`: creación, edición y errores de validación, probado en navegador.
- `/escaneo`: recepción, conforme al permiso de carga del backend.

Nuevas APIs: `GET /api/workspace/resumen/` y `GET /api/actividad/`. Lista de estudios ampliada con nombre del paciente, identificador/estado de informe y parámetro `cola`. Fechas incorrectas o invertidas y paciente inválido responden 400. No se requieren migraciones nuevas para este paquete.

Los filtros de fechas se aplican a la **fecha de registro**. Pacientes/usuarios del tablero son totales actuales; estudios/movimientos corresponden al período indicado. La cola de informes incluye estudios que todavía no tienen informe y excluye repeticiones técnicas. El historial muestra los eventos efectivamente registrados; no se generaron movimientos retrospectivos.

## Validación

- Backend completo: **116 pruebas pasaron**, 0 fallos/errores. Evidencia: `ui-upgrade-backend-full.xml`.
- Frontend: `npm run lint`, sin errores/advertencias; `npm test`, 7 pruebas de sesiones pasaron; `npm run build`, correcto.
- Navegador Edge: 15 comprobaciones funcionales y 3 confirmaciones finales; sin errores de ejecución. Login, alta/edición de pacientes, filtros persistentes, creación/edición de usuarios, lista/detalle, cola de errores, historial por rol y navegación móvil.
- Escritorio 1440×1000 y móvil 390×844: capturas inspeccionadas. Campo 44 px; ancho de página móvil 390 px, sin desbordamiento exterior. Las tablas mantienen desplazamiento horizontal dentro de su contenedor.
- Detector final impeccable: sin incidencias (`ui-upgrade-design-detect.json`).
- Cambios staged preservados byte a byte; 12 archivos de entrenamiento preservados por SHA-256. Sin entrenamiento ni descarga de pesos.

La prueba visual utilizó una base SQLite **separada con datos ficticios**, no las cuentas/pacientes reales. El conector de navegador de Codex falló por el sandbox; la validación se completó con Playwright y Edge locales. Los archivos de pruebas Vitest anteriores no forman parte del comando `npm test` actual; la comprobación del frontend se basa en las 7 pruebas Node y los escenarios de navegador indicados.

## Ver el resultado en el proyecto

Con backend y frontend iniciados normalmente, actualice la página. Si el backend no usa recarga automática, reinícielo para cargar las rutas nuevas. Frontend habitual: `http://localhost:5173`.

```powershell
cd "C:/u/7mo/taller 1/proyecto/neo/neorx/backend"
python manage.py runserver
```

En otra terminal:

```powershell
cd "C:/u/7mo/taller 1/proyecto/neo/neorx/frontend"
npm run dev
```

Para repetir QA aislado: `python docs/ui-preview-server.py` inicia solo una SQLite de prueba en 8001. Frontend de QA requiere `VITE_API_URL=http://localhost:8001/api` y puerto 5174. Los scripts de navegador usan Playwright del runtime instalado; ver `ui-browser-review.cjs` y `ui-browser-confirm.cjs`. Los procesos temporales de QA se cerraron al terminar.

## Capturas con datos ficticios

![Tablero clínico](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/ui-review/dashboard-clinica-desktop.png)

![Administración](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/ui-review/dashboard-admin-desktop.png)

![Pacientes](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/ui-review/pacientes-desktop.png)

![Formulario móvil](C:/u/7mo/taller 1/proyecto/neo/neorx/docs/ui-review/paciente-form-mobile.png)

Las propuestas adicionales de expediente clínico con pestañas y perfil/sesiones siguen en `frontend-mejoras-propuesta.md`; quedan fuera del primer paquete aprobado.
