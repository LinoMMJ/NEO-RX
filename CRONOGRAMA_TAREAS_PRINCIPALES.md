# CRONOGRAMA DE ACTIVIDADES — Neo RX (Versión Tareas Principales)
**Proyecto de Grado: Plataforma de Diagnóstico Asistido por IA para Radiografías de Tórax**

---

## 📅 **Información General**
| Concepto | Valor |
|----------|-------|
| **Inicio** | Martes 25 de agosto de 2026 |
| **Fin** | Viernes 20 de noviembre de 2026 |
| **Duración** | 13 semanas |
| **Fecha actual** | Lunes 8 de septiembre de 2026 (Semana 3) |

---

## 📋 **CRONOGRAMA SEMANAL (FORMATO TABLA)**

| No | ACTIVIDAD | AGO | SEPTIEMBRE | OCTUBRE | NOVIEMBRE | Semanas | % Avance |
|----|-----------|-----|------------|---------|-----------|---------|----------|
|    |           | 3  4 | 1  2  3  4  5 | 1  2  3  4 | 1  2  3  4 |         |          |
|    | Inicio Sem | 11 18 25 | 1  8 15 22 29 | 6 13 20 27 | 3 10 17 24 |         |          |
| **1** | **Configuración proyecto: Git, Docker Compose, Django, variables entorno** | ██ ██ | | | | 2 | 100% ✅ |
| **2** | **Autenticación JWT + RBAC: CustomUser, roles, login/refresh, rol en token** | ██ ██ | | | | 2 | 100% ✅ |
| **3** | **Base de datos: Modelos Paciente, Estudio, migraciones, admin Django** | ██ ██ | | | | 2 | 100% ✅ |
| **4** | **API REST Pacientes/Estudios: CRUD completo, búsqueda, serializers, URLs** | | ██ ██ | | | 2 | 100% ✅ |
| **5** | **Frontend base: Login, Guards JWT, Dashboard contadores, Layout responsive** | | ██ ██ | | | 2 | 100% ✅ |
| **6** | **Módulo Pacientes UI: Tabla, modal crear/editar, búsqueda por CI, paginación** | | ██ ██ | | | 2 | 100% ✅ |
| **7** | **Carga DICOM: Upload multipart, conversión PNG, corrección MONOCHROME1** | | | ██ ██ | | 2 | 100% ✅ |
| **8** | **Validación imagen: Nitidez (Laplaciana OpenCV), detección proyección PA/AP/LAT** | | | ██ ██ | | 2 | 100% ✅ |
| **9** | **Procesamiento asíncrono: Celery + Redis, tareas inferencia, polling estado** | | | ██ ██ | | 2 | 100% ✅ |
| **10** | **Escaneo UI: Drag-drop DICOM, vista previa, progreso, visualizador zoom/pan** | | | ██ ██ | | 2 | 100% ✅ |
| **11** | **Integración CNN: torchxrayvision ResNet-50, wrapper singleton, preprocesado 512x512** | | | | ██ ██ ██ | 3 | 90% 🔄 |
| **12** | **Patologías clínicas: Mapeo 18→14 neumológicas, probabilidades, orden descendente** | | | | ██ ██ ██ | 3 | 90% 🔄 |
| **13** | **Grad-CAM: Heatmap overlay + centroide, endpoint, integración visor frontend** | | | | ██ ██ ██ | 3 | 80% 🔄 |
| **14** | **Niveles clínicos centralizados: Backend niveles.py (Alto/Moderado/Bajo/No sig.), API unificada** | | | | ██ | 1 | 0% ⏳ |
| **15** | **Frontend niveles: Eliminar 5 duplicados umbrales, consumir API niveles backend** | | | | ██ | 1 | 0% ⏳ |
| **16** | **Generación informes: Hallazgos, Impresión, Recomendaciones (reglas + umbrales centralizados)** | | | | | ██ ██ | 2 | 85% 🔄 |
| **17** | **Flujo informes UI: Editor borrador, vista previa, firmar (solo médico), estados** | | | | | ██ ██ | 2 | 85% 🔄 |
| **18** | **Export PDF informes: Plantilla HTML → PDF (weasyprint), descarga, vista previa** | | | | | ██ ██ | 2 | 0% ⏳ |
| **19** | **Export DICOM SR: Structured Report Basic Text SR (pydicom), validación estándar** | | | | | ██ ██ | 2 | 0% ⏳ |
| **20** | **Gestión usuarios Admin: API CRUD usuarios/roles, UI tabla + modal + filtros** | | | | | | ██ | 1 | 0% ⏳ |
| **21** | **Dashboard operativo: Métricas (estudios/día, latencia p95, % completados), gráficos Recharts** | | | | | | ██ | 1 | 0% ⏳ |
| **22** | **Seguridad y auditoría: Encriptación CI/DICOM, logging estructurado, rate limiting, headers** | | | | | | ██ | 1 | 0% ⏳ |
| **23** | **Testing: pytest backend (auth, pacientes, estudios, diagnóstico, informes), vitest frontend** | | | | | | | ██ ██ | 2 | 0% ⏳ |
| **24** | **Documentación API: drf-spectacular Swagger/OpenAPI, docs técnicas, README, arquitectura C4** | | | | | | | ██ ██ | 2 | 0% ⏳ |
| **25** | **Despliegue y entrega: Dockerfiles prod, docker-compose.prod, backup script, tag v1.0, defensa** | | | | | | | | ██ | 1 | 0% ⏳ |
| **26** | **Fine-tuning CNN: Descarga NIH ChestX-ray14, preprocesamiento, splits train/val/test** | | | | | | ██ | 1 | 0% ⏳ |
| **27** | **Fine-tuning CNN: Entrenamiento ResNet-50 (head + partial unfreeze) en RunPod A100** | | | | | | ██ ██ | 2 | 0% ⏳ |
| **28** | **Fine-tuning CNN: Evaluación métricas (AUC, sensibilidad, especificidad por patología)** | | | | | | ██ | 1 | 0% ⏳ |
| **29** | **Fine-tuning CNN: Integración checkpoint en DetectorTorax + validación inferencia** | | | | | | ██ | 1 | 0% ⏳ |
| **30** | **Fine-tuning CNN: Dockerfile.training + scripts reproducibles + docs** | | | | | | ██ | 1 | 0% ⏳ |
| **31** | **Fine-tuning CNN: Comparativa baseline vs fine-tuned + reporte técnico** | | | | | | ██ | 1 | 0% ⏳ |

---

## 🎨 **LEYENDA VISUAL**
- ██ = Semana planificada
- ✅ = **Completado y funcionando** (verificable en demo)
- 🔄 = **En curso / Parcial** (backend listo, falta frontend o pulido)
- ⏳ = **Pendiente** (no iniciado)

---

## 📊 **RESUMEN POR FASES**

| Fase | Tareas | Semanas | Estado Global |
|------|--------|---------|---------------|
| **0. Fundación + Auth** | 1-3 | 2 | ✅ 100% |
| **1. Pacientes + Estudios + UI Base** | 4-6 | 2 | ✅ 100% |
| **2. DICOM + Procesamiento + Async** | 7-10 | 2 | ✅ 100% |
| **3. CNN + Diagnóstico + Grad-CAM** | 11-15 | 4 | 🔄 75% (falta 14-15) |
| **4. Informes + Export** | 16-19 | 4 | 🔄 50% (falta 18-19) |
| **5. Admin + Métricas + Seguridad** | 20-22 | 2 | ⏳ 0% |
| **6. Testing + Docs + Deploy** | 23-25 | 2 | ⏳ 0% |
| **7. Fine-tuning CNN (NUEVO)** | 26-31 | 3 | ⏳ 0% |

---

## ✅ **LO QUE YA FUNCIONA HOY (DEMO LISTA)**

| # | Funcionalidad | Verificación |
|---|---------------|--------------|
| 1-3 | Login JWT + roles, Admin Django, BD | `admin/admin123`, `medico/medico123` |
| 4-6 | Pacientes CRUD + Dashboard + UI | http://localhost:5173 |
| 7-10 | Subir DICOM → PNG → Nitidez → Proyección → Cola CNN | EscaneoPage |
| 11-13 | Inferencia CNN 14 patologías + Grad-CAM heatmap | ResultadoCNN + VisorImagen |

---

## 🔴 **CRÍTICO PARA DEFENSA (PRÓXIMAS 2 SEMANAS)**

| Orden | Tarea | Por qué |
|-------|-------|---------|
| **1** | **Niveles clínicos centralizados (14-15)** | Inconsistencia real: 5 umbrales distintos en frontend |
| **2** | **Export PDF informes (18)** | Entregable tangible esperado en defensa |
| **3** | **Admin usuarios + Dashboard métricas (20-21)** | Requisito explícito documento de grado "gestión" |
| **4** | **Encriptación + Logging (22)** | Compliance médico (HIPAA/LOPD) |
| **5** | **Testing + Swagger + Docker (23-25)** | Calidad académica + reproducibilidad |

---

## 📈 **% AVANCE ESTIMADO POR HITO**

| Hito | Fecha Límite | % Proyecto | Estado |
|------|--------------|------------|--------|
| **MVP Core Funcional** | 21 Sep (Semana 4) | 45% | ✅ **YA ALCANZADO** |
| **IA + Diagnóstico Completo** | 12 Oct (Semana 7) | 60% | ✅ **YA ALCANZADO** |
| **Informes + Export** | 2 Nov (Semana 10) | 70% | 🔄 En curso (falta PDF/DICOM) |
| **Gestión/Admin/Seguridad** | 16 Nov (Semana 12) | 80% | ⏳ Por iniciar |
| **Testing + Docs + Deploy** | 20 Nov (Semana 13) | 90% | ⏳ Por iniciar |
| **Fine-tuning CNN propio** | 27 Nov (Semana 14-15) | 100% | ⏳ Por iniciar |

---

**Generado:** 8 septiembre 2026 | **Basado en código real** (no plan teórico) | **31 tareas principales** | **15-16 semanas (incluye fine-tuning)**