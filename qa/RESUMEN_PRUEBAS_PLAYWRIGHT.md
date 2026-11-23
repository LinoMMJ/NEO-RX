# Evidencia de pruebas automatizadas NeoRX

Fecha de ejecución: 10 de noviembre de 2026
Entorno probado: Docker Compose de producción, Chrome de escritorio, `http://localhost:8080`
Resultado Playwright: **11 de 11 casos aprobados en 35,2 segundos**

## Cobertura funcional y de integración

| Área | Comprobación | Resultado |
|---|---|---|
| Autenticación | Redirección del visitante al login | Aprobado |
| Autenticación | Rechazo seguro de credenciales inválidas | Aprobado |
| RBAC | Acceso válido como médico | Aprobado |
| RBAC | Acceso válido como recepcionista | Aprobado |
| RBAC | Acceso válido como administrador | Aprobado |
| RBAC | Recepción no puede abrir gestión de usuarios | Aprobado |
| Pacientes | Registro, búsqueda, edición y trazabilidad | Aprobado |
| Métricas | Tablero administrativo con métricas operativas | Aprobado |
| Seguridad API | Respuestas 401 y 403; métricas autenticadas | Aprobado |
| Seguridad web | Cabeceras defensivas y JWT en almacenamiento temporal | Aprobado |
| Flujo clínico | Paciente, carga PNG, Celery, CNN, resultado, Grad-CAM e informe | Aprobado |

## Evidencia visual

El reporte HTML contiene las capturas adjuntas de:

- login rechazado sin detalles internos;
- tableros de médico, recepción y administración;
- paciente creado y registro de auditoría;
- métricas administrativas e historial de movimientos;
- resultado CNN para derrame pleural;
- superposición regional Grad-CAM;
- editor del preinforme.

Abrir el reporte con:

```powershell
cd frontend
npm run test:e2e:report
```

Archivo directo: `qa/playwright-report/index.html`.

## Pruebas complementarias

- Vitest: **37 de 37 pruebas unitarias aprobadas** en 8 archivos.
- Pruebas Node de sesión JWT: **7 de 7 aprobadas**.
- Contraste visual: **7 temas aprobados**, con ratios AA comprobados.
- Compilación Vite de producción: **aprobada**.
- Auditoría npm de dependencias de producción: **0 vulnerabilidades conocidas**.

## Alcance técnico

Playwright valida el comportamiento observable y la integración entre React,
Nginx, Django REST, PostgreSQL, Redis y Celery. Las pruebas unitarias de Vitest
se conservan porque cubren funciones y componentes aislados; no se deben
reemplazar por pruebas de navegador. Pytest puede mantenerse para lógica interna
del backend, mientras esta evidencia de la tarea 23 se presenta principalmente
con Playwright por ser reproducible y visual.

## Repetición

Con Docker iniciado:

```powershell
cd frontend
npm run test:e2e
```

Ante un fallo, Playwright conserva captura, video y traza. Para observar la
ejecución en vivo puede usarse `npm run test:e2e:headed`.
