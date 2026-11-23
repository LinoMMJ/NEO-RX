# Evidencia funcional NeoRX con Playwright

Esta suite presenta evidencia reproducible del sistema desplegado en Docker.
Playwright valida la interfaz y la integración HTTP real; no sustituye las
pruebas unitarias internas de Python/React ni constituye validación clínica.

## Cobertura visible

| Bloque | Evidencia |
| --- | --- |
| Autenticación | Acceso correcto por tres roles, rechazo seguro y redirección |
| RBAC | Recepción no puede entrar a gestión administrativa |
| Pacientes | Alta, búsqueda, edición y aparición en auditoría |
| Métricas | Tablero administrativo y endpoint operativo |
| Seguridad | API autenticada, 401/403, cabeceras y almacenamiento temporal JWT |
| Flujo clínico | Carga PNG, Celery, ResNet-50, derrame, Grad-CAM e informe |

## Ejecución

Con Docker iniciado en `http://localhost:8080`:

```powershell
cd frontend
npm run test:e2e
npm run test:e2e:report
```

El reporte navegable se genera en `qa/playwright-report/index.html`. Los casos
exitosos adjuntan capturas; ante un fallo se conservan captura, video y traza.
Las contraseñas se leen desde `.env.docker` y no se incluyen en artefactos.

Para una demostración interactiva:

```powershell
npm run test:e2e:ui
```
