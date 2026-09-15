# CRONOGRAMA DETALLADO DE ACTIVIDADES — Neo RX
**Proyecto de Grado: Plataforma de Diagnóstico Asistido por IA para Radiografías de Tórax**

---

## 📅 **Información General**
| Concepto | Valor |
|----------|-------|
| **Inicio** | Martes 25 de agosto de 2026 |
| **Fin** | Viernes 20 de noviembre de 2026 |
| **Duración total** | 13 semanas (91 días) |
| **Fecha actual** | Lunes 8 de septiembre de 2026 (Semana 3) |
| **Estado general** | **Core MVP funcionando** (Backend Django + Frontend React + CNN inference) |

---

## 🎯 **Resumen de Avance Real vs Planificado**

| Fase | Estado | % Real | Comentario |
|------|--------|--------|------------|
| **Infra & Base** | ✅ Completado | 100% | Django, DB, Auth, Docker-ready |
| **Core Clínico (Pacientes/Estudios/DICOM)** | ✅ Completado | 100% | CRUD + Upload + Validación |
| **IA / CNN Inference** | ✅ Completado | 90% | torchxrayvision integrado, falta fine-tuning propio |
| **Informes Clínicos** | ✅ Completado | 85% | Generación + Firmado, falta PDF/DICOM export |
| **Frontend UI** | ✅ Completado | 90% | 6 páginas funcionales |
| **Testing & Calidad** | ⏳ Pendiente | 10% | Solo tests vacíos |
| **Gestión/Admin/Logging** | ⏳ Pendiente | 0% | Gap identificado en SDD |
| **Despliegue/Entrega** | ⏳ Pendiente | 0% | Docker, CI/CD, docs |
| **Fine-tuning CNN** | ⏳ Pendiente | 0% | NIH ChestX-ray14, RunPod A100, ResNet-50 |

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
| 3.3 | Mapeo 18→14 patologías neumológicas (ES/EN) + orden por probabilidad | `PATOLOGIAS_NEUMOLOGIA` | ✅ |
| 3.4 | Modelo `ResultadoCNN` (OneToOne ImagenDICOM, JSON patologías, tiempo_inferencia) | `diagnostico/models.py` | ✅ |
| 3.5 | Vista `ResultadoCNNView` + serializer (GET resultado por imagen) | `diagnostico/urls.py` | ✅ |
| 3.6 | **Grad-CAM**: Heatmap overlay + centroide (layer4 ResNet) | `gradcam.py` + `GradCAMView` | ✅ |
| 3.7 | Frontend: **ListaPatologias** (badges color: Alto/Moderado/Bajo/No sig.) | `ListaPatologias.jsx` | ✅ |
| 3.8 | Frontend: **BarraFidelidad** (confianza visual por patología) | `BarraFidelidad.jsx` | ✅ |
| 3.9 | Frontend: Integración heatmap Grad-CAM en visor | `VisorImagen.jsx` + overlay | ✅ Parcial |
| 3.10 | Centralizar umbrales clínicos en backend (eliminar 5 duplicados frontend) | `niveles.py` + API devuelve niveles | ⏳ **PENDIENTE CRÍTICO** |

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
| 4.9 | **Export PDF**: xhtml2pdf / weasyprint (plantilla HTML → PDF clínico) | `export_pdf_view` | ⏳ **PENDIENTE** |
| 4.10 | **Export DICOM SR**: pydicom Structured Report (Basic Text SR) | `export_dicom_sr_view` | ⏳ **PENDIENTE** |

---

### **SEMANA 12 (Nov 10 - Nov 16) — FASE 5: GESTIÓN, ADMIN, LOGGING, SEGURIDAD**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 5.1 | **Admin Users CRUD**: API `/api/admin/users/` (listar, crear, editar, desactivar, cambiar rol) | `accounts/admin_views.py` | ⏳ |
| 5.2 | **Admin UI Frontend**: Página `AdminUsuariosPage` (tabla, modal, filtros por rol) | `AdminUsuariosPage.jsx` | ⏳ |
| 5.3 | **Dashboard Operativo**: Métricas tiempo real (estudios/día, latencia p95, % completados) | `GET /api/metrics/operacionales/` | ⏳ |
| 5.4 | Frontend: **DashboardPage** con gráficos (Recharts) + export CSV | `DashboardPage.jsx` + charts | ⏳ |
| 5.5 | **Auditoría/Logging**: Middleware request_id + structured logging (JSON) + modelo `AuditLog` | `logging_config` + `AuditLog` | ⏳ |
| 5.6 | **Encriptación campos sensibles**: `django-cryptography` en `Paciente.ci`, `ImagenDICOM.archivo_dicom` | Migración + campos encrypted | ⏳ |
| 5.7 | **Rate limiting** API (django-ratelimit) + headers seguridad (HSTS, CSP) | `MIDDLEWARE` + settings | ⏳ |
| 5.8 | **Backup strategy**: Script pg_dump + retention + restore test | `scripts/backup.sh` | ⏳ |

---

### **SEMANA 13 (Nov 17 - Nov 20) — FASE 6: TESTING, DOCS, DESPLIEGUE, ENTREGA**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 6.1 | Tests unitarios Backend (pytest): Auth, Pacientes, Estudios, Diagnóstico, Informes | `backend/*/tests.py` > 80% coverage | ⏳ |
| 6.2 | Tests unitarios Frontend (Vitest): Componentes, hooks, utils | `frontend/src/**/*.test.jsx` | ⏳ |
| 6.3 | Tests integración API (DRF APITestCase): Flujos E2E completos | `tests/integration/` | ⏳ |
| 6.4 | Test carga: Locust (100 users concurrentes, upload DICOM + inferencia) | `locustfile.py` + reporte | ⏳ |
| 6.5 | Documentación API: **drf-spectacular** → Swagger UI `/api/schema/swagger/` | OpenAPI 3.0 completo | ⏳ |
| 6.6 | Documentación técnica: README + Arquitectura (C4) + Decisiones (ADR) | `docs/` | ⏳ |
| 6.7 | Dockerfile backend (multi-stage) + frontend (nginx) + docker-compose.prod.yml | `Dockerfile*`, `docker-compose.prod.yml` | ⏳ |
| 6.8 | Variables producción (.env.prod) + secrets management | `.env.prod.example` | ⏳ |
| 6.9 | **Ensayo defensa**: Demo E2E grabada (15 min) + Slides (10 min) | Video + PDF slides | ⏳ |
| 6.10 | Entrega final: Repo tag `v1.0-defensa` + ZIP código + Docs + Video | Release GitHub + Drive | ⏳ |

---

### **SEMANA 14-16 (Nov 23 - Dec 11) — FASE 7: FINE-TUNING CNN PROPIO (NUEVO)**

| # | Tarea Específica | Entregable | Estado |
|---|------------------|------------|--------|
| 7.1 | Descarga NIH ChestX-ray14 (112k imágenes) + metadatos CSV | `data/nih/` + `Data_Entry_2017.csv` | ⏳ |
| 7.2 | Preprocesamiento: resize 512x512, normalización [-1024,1024], splits train/val/test (70/15/15) | `data/nih/processed/` + `splits.json` | ⏳ |
| 7.3 | DataLoader optimizado (num_workers, pin_memory, mixed precision) | `training/dataloaders.py` | ⏳ |
| 7.4 | Modelo: ResNet-50 torchxrayvision + head nueva 14 clases neumológicas | `training/model.py` | ⏳ |
| 7.5 | Entrenamiento: head-only (epochs 1-3) → partial unfreeze layer3-4 (epochs 4-10) en RunPod A100 | `training/train.py` + checkpoints | ⏳ |
| 7.6 | Callbacks: EarlyStopping, ReduceLROnPlateau, ModelCheckpoint, WandB/TensorBoard | `training/callbacks.py` | ⏳ |
| 7.7 | Evaluación: AUC-ROC, sensibilidad, especificidad, F1 por patología + matriz confusión | `training/evaluate.py` + `metrics.json` | ⏳ |
| 7.8 | Comparativa baseline (preentrenado) vs fine-tuned en test set | `training/compare.py` + reporte | ⏳ |
| 7.9 | Export checkpoint final `.pt` + integración en `DetectorTorax.cargar()` | `models/finetuned_resnet50_nih.pt` | ⏳ |
| 7.10 | Dockerfile.training + scripts reproducibles + README.training.md | `Dockerfile.training`, `training/README.md` | ⏳ |

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

## ✅ **TAREAS YA COMPLETADAS (HASTA HOY 8 SEP)**

| Tarea | Completada | Notas |
|-------|------------|-------|
| 0.1 - 0.10 | ✅ | Base sólida |
| 1.1 - 1.10 | ✅ | Pacientes/Estudios + UI |
| 2.1 - 2.10 | ✅ | DICOM upload + validación + CNN async |
| 3.1 - 3.9 | ✅ | CNN + Grad-CAM + UI resultados |
| 4.1 - 4.8 | ✅ | Informes generables y firmables |

---

## 🔴 **TAREAS CRÍTICAS PENDIENTES (BLOQUEANTES PARA DEFENSA)**

| Prioridad | Tarea | Esfuerzo | Riesgo |
|-----------|-------|----------|--------|
| **P0** | Centralizar umbrales clínicos (`niveles.py`) + API devuelve `Alto/Moderado/Bajo/No sig.` | 4h | **Inconsistencia clínica actual** (5 umbrales distintos en frontend) |
| **P0** | Export PDF informes (xhtml2pdf/weasyprint) | 6h | **Entregable tangible esperado** |
| **P1** | Admin Users CRUD + UI | 8h | Requisito grado "gestión" |
| **P1** | Dashboard operativo métricas + gráficos | 8h | Requisito grado "monitoreo" |
| **P1** | Encriptación CI + DICOM (HIPAA/LOPD) | 4h | Compliance médico |
| **P2** | Tests (pytest + vitest) > 60% coverage | 16h | Calidad académica |
| **P2** | Swagger/OpenAPI + docs técnicas | 4h | Presentación profesional |
| **P2** | Docker compose producción + deploy guide | 6h | Reproducibilidad |

---

## 📈 **% AVANCE ESTIMADO POR HITO**

| Hito | Fecha Límite | % Proyecto | Estado |
|------|--------------|------------|--------|
| **MVP Core Funcional** | 21 Sep (Semana 4) | 40% | ✅ **YA ALCANZADO** |
| **IA + Diagnóstico Completo** | 12 Oct (Semana 7) | 55% | ✅ **YA ALCANZADO** |
| **Informes + Export** | 2 Nov (Semana 10) | 65% | 🔄 En curso (falta PDF/DICOM) |
| **Gestión/Admin/Seguridad** | 16 Nov (Semana 12) | 75% | ⏳ Por iniciar |
| **Testing + Docs + Deploy** | 20 Nov (Semana 13) | 85% | ⏳ Por iniciar |
| **Fine-tuning CNN propio** | 11 Dic (Semana 16) | 100% | ⏳ Por iniciar |

---

## ⚠️ **DECISIONES TÉCNICAS CLAVE (ADR) — Para documentar en defensa**

| ADR | Decisión | Justificación |
|-----|----------|---------------|
| **ADR-001** | Django + DRF (no Flask) | Admin auto, ORM maduro, auth robusto, migraciones |
| **ADR-002** | JWT Stateless (SimpleJWT) + RBAC en token | Escalable, sin sesión servidor, frontend simple |
| **ADR-003** | torchxrayvision preentrenado (no modelo propio aún) | Time-to-demo, baseline clínico validado, fine-tuning post-entrega |
| **ADR-004** | Celery + Redis para inferencia async | No bloquea request HTTP, escalable a GPU workers |
| **ADR-005** | SQLite dev / PostgreSQL prod (Docker) | Paridad dev-prod, cero config local |
| **ADR-006** | Centralizar umbrales en backend (Single Source of Truth) | Elimina 5 duplicados frontend, consistencia clínica |
| **ADR-007** | React 19 + Vite + Tailwind 4 (no TypeScript aún) | Velocidad dev, bundle pequeño, migración TS futura |
| **ADR-008** | Fine-tuning ResNet-50 en NIH ChestX-ray14 (head + partial unfreeze) | Modelo propio validado en datos clínicos, mejor que baseline genérico |

---

## 📝 **PRÓXIMOS PASOS INMEDIATOS (ESTA SEMANA 8-14 SEP)**

1. **Lunes 8** → Centralizar umbrales clínicos (`niveles.py`) + actualizar frontend
2. **Martes 9** → Export PDF informes (weasyprint) + test visual
3. **Miércoles 10** → Admin Users CRUD API + UI básica
4. **Jueves 11** → Dashboard métricas + Recharts
5. **Viernes 12** → Encriptación CI + Logging estructurado
6. **Sáb-Dom** → Tests pytest (mínimo happy paths) + Swagger

---

## 🧠 **PRÓXIMOS PASOS FINE-TUNING (SEMANA 14-16, NOV 23 - DIC 11)**

1. **Semana 14** → Descarga NIH + preprocesamiento + DataLoader + modelo head-only
2. **Semana 15** → Entrenamiento RunPod A100 (head 3 epochs → unfreeze layer3-4 7 epochs)
3. **Semana 16** → Evaluación métricas + comparativa baseline vs fine-tuned + integración + docs

---

**Documento generado:** 8 de septiembre de 2026  
**Versión:** 1.1 — Agregada Fase 7 Fine-tuning CNN  
**Responsable:** [Tu Nombre] — Proyecto de Grado Neo RX