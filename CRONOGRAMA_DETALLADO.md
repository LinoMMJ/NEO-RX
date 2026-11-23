# CRONOGRAMA DETALLADO DE ACTIVIDADES — Neo RX
**Proyecto de Grado: Plataforma de Diagnóstico Asistido por IA para Radiografías de Tórax**

---

## 📅 **Información General**
| Concepto | Valor |
|----------|-------|
| **Inicio** | Martes 25 de agosto de 2026 |
| **Fin** | Viernes 20 de noviembre de 2026 |
| **Duración total** | 13 semanas (91 días) |
| **Fecha actual** | Martes 20 de octubre de 2026 (Semana 9) |
| **Próxima presentación** | Miércoles 21 de octubre de 2026 |
| **Estado general** | **Fase 3 lista para demostración y fases posteriores adelantadas** |

---

## 🎯 **Resumen de Avance Real vs Planificado**

| Fase | Estado | % Real | Comentario |
|------|--------|--------|------------|
| **Infra & Base** | ✅ Completado | 100% | Django, DB, Auth, Docker-ready |
| **Core Clínico (Pacientes/Estudios/DICOM)** | ✅ Completado | 100% | CRUD + Upload + Validación |
| **IA / CNN Inference** | ✅ Completado | 100% | Modelo focused5 integrado y Grad-CAM verificado |
| **Informes Clínicos** | ✅ Completado | 100% | Generación, firma, PDF y DICOM SR probados |
| **Frontend UI** | ✅ Completado | 95% | Flujos clínicos y administrativos funcionales |
| **Testing & Calidad** | ✅ Completado para la tarea 23 | 100% | Playwright 11/11, Vitest 37/37 y Node 7/7; evidencia HTML visual |
| **Gestión/Admin/Logging** | ✅ Completado | 90% | CRUD, actividad, auditoría y métricas disponibles |
| **Despliegue/Entrega** | 🔄 En curso | 75% | Docker y scripts listos; falta ensayo y paquete final |
| **Fine-tuning CNN** | 🔄 En curso | 85% | Entrenamiento focused5 concluido; falta evaluación final independiente |

---

## 📋 **CRONOGRAMA DETALLADO POR SEMANAS**

### **SEMANA 1-2 (Ago 25 - Sep 7) — FASE 0: FUNDACIÓN Y AUTENTICACIÓN** ✅ COMPLETADO

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 0.1 | Inicializar repo Git + .gitignore + README | Repo versionado | ✅ |
| 0.2 | Configurar Docker Compose (PostgreSQL + Redis + Backend + Frontend) | `docker-compose.yml` funcional | ✅ Parcial (config manual) |
| 0.3 | Crear proyecto Django 5.2 + DRF + apps base | Estructura `backend/` | ✅ |
| 0.4 | Configurar `CustomUser` con roles (medico/tecnico/administrador) | `accounts/models.py` | ✅ |
| 0.5 | Implementar JWT Authentication (SimpleJWT) | `POST /api/token/`, `POST /api/token/refresh/` | ✅ |
| 0.6 | Agregar `rol` al payload JWT + serializer personalizado | Token incluye rol + nombre | ✅ |
| 0.7 | Configurar CORS para frontend (localhost:5173) | `CORS_ALLOWED_ORIGINS` | ✅ |
| 0.8 | Crear superusuario admin + usuario médico de prueba | Credenciales funcionales | ✅ |
| 0.9 | Configurar variables de entorno (.env.example) | Plantilla documentada | ✅ |
| 0.10 | Migraciones iniciales + BD SQLite para desarrollo local | `db.sqlite3` limpia | ✅ |

---

### **SEMANA 3-4 (Sep 8 - Sep 21) — FASE 1: MÓDULO PACIENTES Y ESTUDIOS** ✅ MAYORITARIO COMPLETADO

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 1.1 | Modelo `Paciente` (CI único, nombres, fecha_nac, género, teléfono) | `pacientes/models.py` | ✅ |
| 1.2 | Modelo `Estudio` (FK Paciente, fecha, tipo, observaciones, estado) | `pacientes/models.py` | ✅ |
| 1.3 | Serializers con validación CI único + nested estudios | `pacientes/serializers.py` | ✅ |
| 1.4 | ViewSet `PacienteViewSet` (CRUD completo + búsqueda por CI) | `GET/POST/PUT/DELETE /api/pacientes/` | ✅ |
| 1.5 | ViewSet `EstudioViewSet` (CRUD + filtro por paciente/estado/fecha) | `GET/POST/PUT/DELETE /api/estudios/` | ✅ |
| 1.6 | URLs REST versionadas (`/api/pacientes/`, `/api/estudios/`) | `pacientes/urls.py` | ✅ |
| 1.7 | Frontend: Página **Login** + guards por rol (JWT en localStorage) | `LoginPage.jsx`, `ProtectedRoute` | ✅ |
| 1.8 | Frontend: **Dashboard** con contadores (hoy/pendientes/total) | `DashboardPage.jsx` | ✅ |
| 1.9 | Frontend: **Módulo Pacientes** (tabla, modal crear/editar, búsqueda) | `PacientesPage.jsx` | ✅ |
| 1.10 | Frontend: Integración API pacientes/estudios (Axios + interceptors) | `src/api/` | ✅ |

---

### **SEMANA 5-6 (Sep 22 - Oct 5) — FASE 2: CARGA Y PROCESAMIENTO DICOM**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 2.1 | Modelo `ImagenDICOM` (FK Estudio, FileField, PNG derivado, metadatos) | `estudios/models.py` | ✅ |
| 2.2 | Endpoint `POST /api/estudios/{id}/imagenes/` (upload multipart) | `UploadDICOMView` | ✅ |
| 2.3 | Conversión DICOM → PNG (pydicom + corrección MONOCHROME1) | `_dicom_a_png()` en `utils.py` | ✅ |
| 2.4 | **Validación nitidez**: Varianza Laplaciana (OpenCV) umbral 100.0 | `calcular_borrosidad()` | ✅ |
| 2.5 | **Detección proyección**: PA/AP/LAT desde tags DICOM + fallback heurístico | `detect_projection_type()` | ✅ |
| 2.6 | Estados de procesamiento: `pendiente` → `procesando` → `procesado`/`error` | Campo `estado_procesamiento` | ✅ |
| 2.7 | Tarea Celery asíncrona para inferencia CNN (no bloquea request) | `procesar_imagen_task` | ✅ |
| 2.8 | Endpoint polling `GET /api/diagnostico/tarea/{task_id}/` | Estado + resultado parcial | ✅ |
| 2.9 | Frontend: **EscaneoPage** (drag-drop, progreso, vista previa PNG) | `EscaneoPage.jsx` | ✅ |
| 2.10 | Frontend: Visualizador DICOM/PNG con zoom/pan (VisorImagen) | `VisorImagen.jsx` | ✅ |

---

### **SEMANA 7-9 (Oct 6 - Oct 26) — FASE 3: INTEGRACIÓN CNN Y DIAGNÓSTICO**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 3.1 | Wrapper `DetectorTorax` (Singleton) con torchxrayvision ResNet-50 | `diagnostico/services.py` | ✅ |
| 3.2 | Preprocesamiento idéntico a xrv: CenterCrop 512 + Resize 512 + Normalize [-1024,1024] | `_preprocesar()` | ✅ |
| 3.3 | Cinco categorías focused5 (ES/EN) y orden por puntuación | Metadatos del checkpoint | ✅ |
| 3.4 | Modelo `ResultadoCNN` (OneToOne ImagenDICOM, JSON patologías, tiempo_inferencia) | `diagnostico/models.py` | ✅ |
| 3.5 | Vista `ResultadoCNNView` + serializer (GET resultado por imagen) | `diagnostico/urls.py` | ✅ |
| 3.6 | **Grad-CAM**: Heatmap overlay + centroide (layer4 ResNet) | `gradcam.py` + `GradCAMView` | ✅ |
| 3.7 | Frontend: **ListaPatologias** (señales según threshold y nivel visual devuelto por backend) | `ListaPatologias.jsx` | ✅ |
| 3.8 | Frontend sin umbrales duplicados ni “confianza diagnóstica”; degradación neutral si falla la API | `ListaPatologias.jsx` | ✅ |
| 3.9 | Frontend: Integración heatmap Grad-CAM en visor | `VisorImagen.jsx` + overlay | ✅ |
| 3.10 | Centralizar niveles visuales en backend y mantener separados los thresholds del checkpoint | `niveles.py` + API unificada | ✅ |

---

### **SEMANA 10-11 (Oct 27 - Nov 9) — FASE 4: INFORMES CLÍNICOS Y EXPORT**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 4.1 | Modelo `InformePreliminar` (1:1 Estudio, FK Médico, estado: borrador/revisado/firmado) | `informes/models.py` | ✅ |
| 4.2 | Generación texto **Hallazgos** (reglas por patología + umbrales centralizados) | `generar_texto_hallazgos()` | ✅ |
| 4.3 | Generación **Impresión Diagnóstica** (resumen priorizado) | `generar_impresion()` | ✅ |
| 4.4 | Generación **Recomendaciones** (seguimiento, estudios complementarios) | `generar_recomendaciones()` | ✅ |
| 4.5 | Endpoint `POST /api/informes/{estudio_id}/generar/` (crea borrador auto) | `generar_informe_view` | ✅ |
| 4.6 | Endpoint `PUT /api/informes/{id}/` (editar hallazgos/impresión/recomendaciones) | Editable solo en borrador | ✅ |
| 4.7 | Endpoint `POST /api/informes/{id}/firmar/` (solo rol=medico, timestamp) | `firmar_informe_view` | ✅ |
| 4.8 | Frontend: **InformePage** (editor rico + vista previa + botón firmar) | `InformePage.jsx` | ✅ |
| 4.9 | **Export PDF**: documento clínico descargable | `DescargarInformePDFView` | ✅ |
| 4.10 | **Export DICOM SR**: pydicom Structured Report | `DescargarInformeDICOMSRView` | ✅ |

---

### **SEMANA 12 (Nov 10 - Nov 16) — FASE 5: GESTIÓN, ADMIN, LOGGING, SEGURIDAD**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 5.1 | **Admin Users CRUD**: API `/api/admin/users/` | API administrativa | ✅ |
| 5.2 | **Admin UI Frontend**: tabla, modal y filtros por rol | `AdminUsuariosPage.jsx` | ✅ |
| 5.3 | **Dashboard Operativo**: métricas, latencia y completitud | `GET /api/metrics/operacionales/` | ✅ |
| 5.4 | Frontend: tablero con gráficos y export CSV | `DashboardPage.jsx` + charts | 🔄 Métricas listas; faltan gráficos/CSV |
| 5.5 | **Auditoría/Logging**: request_id, logging y `AuditLog` | Seguridad y actividad | ✅ |
| 5.6 | **Protección de datos**: CI cifrado y entrega autenticada de imágenes | Campos + media privada | 🔄 Falta cifrado binario del volumen |
| 5.7 | **Rate limiting** API + headers de seguridad | Middleware + settings | ✅ |
| 5.8 | **Backup strategy**: pg_dump, retención y verificación | `scripts/backup.sh` | ✅ Script; falta ensayo de restauración |

---

### **SEMANA 13 (Nov 17 - Nov 20) — FASE 6: TESTING, DOCS, DESPLIEGUE, ENTREGA**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 6.1 | Tests Backend: Auth, Pacientes, Estudios, Diagnóstico, Informes y training | 163 pruebas pasan; falta medir cobertura | 🔄 |
| 6.2 | Tests unitarios frontend: componentes, hooks, utils y sesión | 37 Vitest + 7 Node aprobados; contraste de 7 temas | ✅ |
| 6.3 | Playwright funcional e integración: auth, RBAC, pacientes, auditoría, métricas, seguridad y flujo clínico | 11/11 aprobados; reporte HTML con 11 capturas | ✅ |
| 6.4 | Test carga: Locust (100 users concurrentes, upload DICOM + inferencia) | `locustfile.py` + reporte | ⏳ |
| 6.5 | Documentación API: Swagger UI `/api/schema/swagger/` | Disponible; faltan esquemas de varios `APIView` | 🔄 |
| 6.6 | Documentación técnica: README + decisiones y revisiones | `docs/` | 🔄 |
| 6.7 | Dockerfiles + nginx + docker-compose.prod.yml | Despliegue reproducible | ✅ |
| 6.8 | Variables producción (.env.prod) + secrets management | `.env.prod.example` | ⏳ |
| 6.9 | **Ensayo defensa**: Demo E2E grabada (15 min) + Slides (10 min) | Video + PDF slides | ⏳ |
| 6.10 | Entrega final: Repo tag `v1.0-defensa` + ZIP código + Docs + Video | Release GitHub + Drive | ⏳ |

---

### **SEMANA 14-16 (Nov 23 - Dec 11) — FASE 7: FINE-TUNING CNN PROPIO (NUEVO)**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 7.1 | Descarga NIH ChestX-ray14 (112k imágenes) + metadatos CSV | `data/nih/` + `Data_Entry_2017.csv` | ⏳ |
| 7.2 | Preprocesamiento 512x512, normalización y splits por paciente | Manifiestos focused5 | ✅ |
| 7.3 | DataLoader optimizado y precisión mixta | `training/dataset.py` | ✅ |
| 7.4 | ResNet-50 con cabeza de cinco categorías | `training/model.py` | ✅ |
| 7.5 | Entrenamiento head-only + fine-tuning | Checkpoint focused5 | ✅ |
| 7.6 | Early stopping, scheduler, checkpoints y TensorBoard | Pipeline de entrenamiento | ✅ |
| 7.7 | Métricas por categoría y selección de thresholds | Validación lista; test final pendiente | 🔄 |
| 7.8 | Comparativa baseline (preentrenado) vs fine-tuned en test set | `training/compare.py` + reporte | ⏳ |
| 7.9 | Export checkpoint final `.pt` + integración en `DetectorTorax.cargar()` | `neorx_focused5_resnet50.pt` | ✅ |
| 7.10 | Dockerfile.training + scripts reproducibles + documentación | Pipeline reproducible | ✅ |

---

## 📊 **VISTA SEMANAL RESUMIDA (GRÁFICO GANTT TEXTUAL)**

```
SEMANA:    1  2  3  4  5  6  7  8  9  10 11 12 13 14 15 16
           ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ──
FASE 0:    ██ ██
FASE 1:       ██ ██
FASE 2:          ██ ██
FASE 3:             ██ ██ ██
FASE 4:                  ██ ██
FASE 5:                       ██
FASE 6:                           ██
FASE 7:                                     ██ ██ ██
```

---

## ✅ **TAREAS YA COMPLETADAS (VERIFICADAS EL 20 OCT)**

| Tarea | Completada | Notas |
|-------|------------|-------|
| 0.1 - 0.10 | ✅ | Base sólida |
| 1.1 - 1.10 | ✅ | Pacientes/Estudios + UI |
| 2.1 - 2.10 | ✅ | DICOM upload + validación + CNN async |
| 3.1 - 3.10 | ✅ | Focused5 + thresholds + Grad-CAM + UI resultados |
| 4.1 - 4.10 | ✅ | Informes, firma, PDF y DICOM SR |
| 5.1 - 5.3 | ✅ | Administración de usuarios y métricas operativas |
| 5.5 - 5.8 | ✅ | Auditoría, protección de CI, seguridad y backup |

---

## 🔴 **TAREAS CRÍTICAS PENDIENTES (BLOQUEANTES PARA DEFENSA)**

| Prioridad | Tarea | Esfuerzo | Riesgo |
|-----------|-------|----------|--------|
| **P0** | Evaluación final sobre test + comparación con baseline | 6h | No afirmar desempeño clínico solo con validación |
| **P0** | Preparar estudios y plan de contingencia para la demo | 2h | Evitar depender de carga o red durante la exposición |
| **P1** | Completar esquemas OpenAPI de endpoints `APIView` | 4h | Swagger todavía omite operaciones |
| **P1** | Dashboard con gráficos y exportación CSV | 6h | Visualización operativa incompleta |
| **P1** | Medir cobertura y completar rutas sin pruebas | 8h | Falta porcentaje formal de cobertura |
| **P2** | Ensayo de defensa, capturas y video | 6h | Entrega final y contingencia |
| **P2** | Prueba de carga y restauración de backup | 6h | Evidencia operativa pendiente |

---

## 📈 **% AVANCE ESTIMADO POR HITO**

| Hito | Fecha Límite | % Proyecto | Estado |
|------|--------------|------------|--------|
| **MVP Core Funcional** | 21 Sep (Semana 4) | 40% | ✅ **YA ALCANZADO** |
| **IA + Diagnóstico Completo** | 12 Oct (Semana 7) | 55% | ✅ **ALCANZADO** |
| **Informes + Export** | 2 Nov (Semana 10) | 65% | ✅ **ADELANTADO** |
| **Gestión/Admin/Seguridad** | 16 Nov (Semana 12) | 75% | 🔄 90% adelantado |
| **Testing + Docs + Deploy** | 20 Nov (Semana 13) | 85% | 🔄 75% adelantado |
| **Fine-tuning focused5** | 11 Dic (Semana 16) | 100% | 🔄 Integrado; falta evaluación final |

---

## ⚠️ **DECISIONES TÉCNICAS CLAVE (ADR) — Para documentar en defensa**

| ADR | Decisión | Justificación |
|-----|----------|---------------|
| **ADR-001** | Django + DRF (no Flask) | Admin auto, ORM maduro, auth robusto, migraciones |
| **ADR-002** | JWT Stateless (SimpleJWT) + RBAC en token | Escalable, sin sesión servidor, frontend simple |
| **ADR-003** | Baseline torchxrayvision conservado como referencia | Permite comparar el modelo propio con una línea base reproducible |
| **ADR-004** | Celery + Redis para inferencia async | No bloquea request HTTP, escalable a GPU workers |
| **ADR-005** | SQLite dev / PostgreSQL prod (Docker) | Paridad dev-prod, cero config local |
| **ADR-006** | Centralizar umbrales en backend (Single Source of Truth) | Elimina 5 duplicados frontend, consistencia clínica |
| **ADR-007** | React 19 + Vite + Tailwind 4 (no TypeScript aún) | Velocidad dev, bundle pequeño, migración TS futura |
| **ADR-008** | Fine-tuning ResNet-50 para cinco categorías NIH | Reduce ambigüedad; la mejora frente al baseline aún debe medirse en test |

---

## 📝 **PRÓXIMOS PASOS INMEDIATOS (20-26 OCT)**

1. **Martes 20** → Integrar y verificar checkpoint focused5; ejecutar suites completas
2. **Miércoles 21** → Presentar Fase 3 con demo preparada y estudio de respaldo
3. **Jueves 22** → Evaluar checkpoint sobre test y comparar con baseline
4. **Viernes 23** → Completar esquemas OpenAPI pendientes
5. **Sábado 24** → Añadir gráficos y exportación CSV al tablero
6. **Domingo 25** → Medir cobertura y preparar evidencias de la siguiente entrega

---

## 🧠 **PRÓXIMOS PASOS FINE-TUNING (SEMANA 14-16, NOV 23 - DIC 11)**

1. **Completado anticipadamente** → Preparación, splits, DataLoader y entrenamiento focused5
2. **Siguiente** → Evaluación final en test, análisis por clase y por proyección
3. **Cierre** → Comparativa baseline, informe metodológico y evidencia reproducible

---

**Documento actualizado:** 20 de octubre de 2026

**Versión:** 1.2 — Estado verificado para la presentación del 21 de octubre

**Responsable:** [Tu Nombre] — Proyecto de Grado Neo RX
