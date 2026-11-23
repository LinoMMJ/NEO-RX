# CRONOGRAMA DE ACTIVIDADES — Neo RX (Versión Tareas Principales)
**Proyecto de Grado: Plataforma de Diagnóstico Asistido por IA para Radiografías de Tórax**

---

## 📅 **Información General**
| Concepto | Valor |
|----------|-------|
| **Inicio** | Martes 25 de agosto de 2026 |
| **Fin** | Viernes 20 de noviembre de 2026 |
| **Duración** | 13 semanas |
| **Fecha actual** | Martes 20 de octubre de 2026 (Semana 9) |
| **Próxima presentación** | Miércoles 21 de octubre de 2026 |

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
| **11** | **Integración CNN: ResNet-50 focused5, wrapper singleton, preprocesado 512x512** | | | | ██ ██ ██ | 3 | 100% ✅ |
| **12** | **Cinco categorías: puntuaciones, thresholds de validación y orden descendente** | | | | ██ ██ ██ | 3 | 100% ✅ |
| **13** | **Grad-CAM: Heatmap overlay + centroide, endpoint, integración visor frontend** | | | | ██ ██ ██ | 3 | 100% ✅ |
| **14** | **Niveles visuales centralizados y thresholds del checkpoint** | | | | ██ | 1 | 100% ✅ |
| **15** | **Frontend niveles: consumo exclusivo de API backend; sin umbrales ni fallback locales** | | | | ██ | 1 | 100% ✅ |
| **16** | **Generación informes: Hallazgos, Impresión, Recomendaciones (reglas + thresholds)** | | | | | ██ ██ | 2 | 100% ✅ |
| **17** | **Flujo informes UI: Editor, checklist, revisión y firma médica** | | | | | ██ ██ | 2 | 100% ✅ |
| **18** | **Export PDF informes: documento clínico, descarga y validación** | | | | | ██ ██ | 2 | 100% ✅ |
| **19** | **Export DICOM SR: Structured Report con pydicom** | | | | | ██ ██ | 2 | 100% ✅ |
| **20** | **Gestión usuarios Admin: API CRUD usuarios/roles, UI tabla + modal + filtros** | | | | | | ██ | 1 | 100% ✅ |
| **21** | **Dashboard operativo: métricas y tablero; faltan gráficos/CSV** | | | | | | ██ | 1 | 70% 🔄 |
| **22** | **Seguridad y auditoría: CI cifrado, media privada, logging, rate limiting** | | | | | | ██ | 1 | 85% 🔄 |
| **23** | **Testing: Playwright E2E/integración + Vitest/Node unitario** | | | | | | | ██ ██ | 2 | 100% ✅ |
| **24** | **Documentación API y técnica** | | | | | | | ██ ██ | 2 | 70% 🔄 |
| **25** | **Despliegue y entrega: Docker, backup y preparación de defensa** | | | | | | | | ██ | 1 | 75% 🔄 |
| **26** | **Fine-tuning: preparación NIH y splits focused5** | | | | | | ██ | 1 | 100% ✅ |
| **27** | **Fine-tuning ResNet-50 (head + unfreeze)** | | | | | | ██ ██ | 2 | 100% ✅ |
| **28** | **Evaluación por categoría** | | | | | | ██ | 1 | 70% 🔄 |
| **29** | **Integración checkpoint y validación de inferencia** | | | | | | ██ | 1 | 100% ✅ |
| **30** | **Dockerfile.training + scripts reproducibles + docs** | | | | | | ██ | 1 | 100% ✅ |
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
| **3. CNN + Diagnóstico + Grad-CAM** | 11-15 | 4 | ✅ 100% |
| **4. Informes + Export** | 16-19 | 4 | ✅ 100% adelantado |
| **5. Admin + Métricas + Seguridad** | 20-22 | 2 | 🔄 90% adelantado |
| **6. Testing + Docs + Deploy** | 23-25 | 2 | 🔄 75% adelantado |
| **7. Fine-tuning focused5** | 26-31 | 3 | 🔄 85% adelantado |

---

## ✅ **LO QUE YA FUNCIONA HOY (DEMO LISTA)**

| # | Funcionalidad | Verificación |
|---|---------------|--------------|
| 1-3 | Login JWT + roles, Admin Django, BD | `admin/admin123`, `medico/medico123` |
| 4-6 | Pacientes CRUD + Dashboard + UI | http://localhost:5173 |
| 7-10 | Subir DICOM → PNG → Nitidez → Proyección → Cola CNN | EscaneoPage |
| 11-15 | Inferencia focused5 + thresholds por clase + Grad-CAM | ResultadoCNN + VisorImagen |
| 16-19 | Informe, firma, PDF y DICOM SR | InformePage + exportaciones |
| 20-22 | Usuarios, métricas, auditoría y seguridad | Administración + actividad |

---

## 🔴 **CRÍTICO PARA DEFENSA (PRÓXIMAS 2 SEMANAS)**

| Orden | Tarea | Por qué |
|-------|-------|---------|
| **1** | **Evaluación final focused5 en test** | Validación no sustituye una medición independiente |
| **2** | **Completar OpenAPI de los `APIView`** | Swagger aún omite varias operaciones |
| **3** | **Gráficos y CSV del tablero** | Completar el entregable de monitoreo |
| **4** | **Cobertura y pruebas de carga** | Aportar evidencia cuantitativa de calidad |
| **5** | **Ensayo, capturas y video** | Reducir riesgo en la defensa final |

---

## 📈 **% AVANCE ESTIMADO POR HITO**

| Hito | Fecha Límite | % Proyecto | Estado |
|------|--------------|------------|--------|
| **MVP Core Funcional** | 21 Sep (Semana 4) | 45% | ✅ **YA ALCANZADO** |
| **IA + Diagnóstico Completo** | 12 Oct (Semana 7) | 60% | ✅ **ALCANZADO** |
| **Informes + Export** | 2 Nov (Semana 10) | 70% | ✅ **ADELANTADO** |
| **Gestión/Admin/Seguridad** | 16 Nov (Semana 12) | 80% | 🔄 90% adelantado |
| **Testing + Docs + Deploy** | 20 Nov (Semana 13) | 90% | 🔄 75% adelantado |
| **Fine-tuning focused5** | 27 Nov (Semana 14-15) | 100% | 🔄 Integrado; falta evaluación final |

---

**Actualizado:** 20 octubre 2026 | **Verificado con pruebas y build** | **31 tareas principales** | **15-16 semanas (incluye fine-tuning)**
