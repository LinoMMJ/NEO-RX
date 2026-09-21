# Revisión Metodológica del Pipeline ML — Neo RX

**Fecha**: 2026-09-16
**Versión**: 1.0
**Estado**: Pre-entrenamiento (auditoría completada, correcciones aplicadas)

---

## Resumen Ejecutivo

Este documento registra la revisión crítica del plan de implementación original contra los requisitos de rigor académico para el proyecto de grado "Sistema Web de Apoyo a la Interpretación Radiológica". Se identificaron **7 problemas críticos** y **10 problemas metodológicos** que invalidarían los resultados si no se corrigen.

---

## 1. Partes del Plan Original que Eran Correctas

| Aspecto | Estado | Comentario |
|---------|--------|------------|
| Arquitectura ResNet-50 + torchxrayvision | Correcta | Transfer learning apropiado |
| Division patient-level (70/15/15) | Correcta | Código ya existía en prepare_dataset.py |
| Clasificación multi-label (BCEWithLogitsLoss) | Correcta | Apropiado para hallazgos múltiples |
| Two-stage training (head -> partial unfreeze) | Correcta | Estándar en fine-tuning |
| Grad-CAM implementado | Correcta | Interpretabilidad disponible |
| Integración Django + Celery | Correcta | Arquitectura async funcional |
| Singleton DetectorTorax | Correcta | Carga eficiente en memoria |

---

## 2. Partes Corregidas (Problemas Críticos)

### C1: PyTorch CPU-only en entorno con GPU
**Problema**: PyTorch 2.12.0+cpu instalado; RTX 3050 6GB no utilizable.
**Corrección**: Verificar compatibilidad entre Python, PyTorch, torchvision y CUDA en el entorno destinado a Fase 3. No se verificó aquí un runtime CUDA.
**Archivo**: Configuración CUDA pendiente de validación; no ejecutar instalación o entrenamiento durante Fase 2.1.

### C2: Dataset NIH no descargado
**Problema**: data/nih/ no existe.
**Corrección**: Descarga manual desde NIH Box / Kaggle -> colocar en data/nih/images/ + Data_Entry_2017.csv.
**Archivo**: prepare_dataset.py ya valida estructura local.

### C3: Data Leakage en Thresholds (CRITICO)
**Problema**: evaluate.py linea 116 calculaba threshold optimo (Youden's J) SOBRE TEST set.
**Corrección**:
- threshold_optimizer.py nuevo: optimiza SOLO en VALIDATION
- train.py guarda thresholds en checkpoint tras cada best epoch
- evaluate.py reescrito: usa checkpoint["thresholds"], NO recalcula
**Archivos**: threshold_optimizer.py (nuevo), train.py, evaluate.py, model.py

### C4: Sin Data Augmentation en TRAIN
**Problema**: Mismos transforms (CenterCrop + Resize) para train/val/test.
**Corrección**: dataset.py reescrito con build_train_transform() (augmentation) vs build_eval_transform() (solo preprocesamiento). Configurable via config.yaml['augmentation'].
**Archivos**: dataset.py, config.yaml

### C5: Sin pos_weight para Desbalance Severo
**Problema**: NIH tiene desbalance extremo (Hernia 0.2%, Infiltration 18%). BCEWithLogitsLoss sin pos_weight.
**Corrección**: train.py calcula pos_weight = n_neg / n_pos EXCLUSIVAMENTE desde TRAIN loader. Guardado en checkpoint.
**Archivos**: train.py, model.py, config.yaml

### C6: Thresholds Hardcoded en Backend (niveles.py)
**Problema**: Umbrales clínicos inventados (ej. Neumonía alto=0.60) sin base experimental.
**Corrección**:
- niveles.py reescrito: separa thresholds modelo (del checkpoint, decisión binaria) de niveles visuales (UI, codificación color)
- API /api/niveles-clinicos/ documenta la distinción
**Archivos**: niveles.py, views_niveles.py

### C7: Métricas Inventadas en README
**Problema**: Tabla "Expected Metrics" con valores numéricos (AUC >0.85, etc.).
**Corrección**: Eliminada tabla completa. Reemplazada por: "Todas las métricas son PENDIENTE DE EJECUCIÓN EXPERIMENTAL."
**Archivo**: README.training.md

---

## 3. Partes Corregidas (Problemas Metodológicos)

| # | Problema Original | Corrección Aplicada |
|---|-------------------|---------------------|
| M1 | prepare_dataset.py solo imprimía warning de overlap | validate_patient_overlap() -> sys.exit(1) si overlap > 0 |
| M2 | No generaba dataset_statistics.csv | generate_dataset_statistics() crea CSV + JSON obligatorios |
| M3 | evaluate.py usaba NIH_LABELS hardcoded (14) | Usa model.pathologies (12 pulmonares) del checkpoint |
| M4 | No había inference.py standalone | Creado inference.py con load_model(), predict(), predict_from_file() |
| M5 | No había experiment tracking | Creado experiment_tracker.py con estructura experiments/exp_XXX/ |
| M6 | Checkpoint no guardaba thresholds ni pos_weight | save_checkpoint() extendido con thresholds, pos_weight |
| M7 | DetectorTorax hacía fallback silencioso a baseline | Ahora ERROR explícito si NEORX_MODEL_PATH configurado pero archivo no existe |
| M8 | Terminología "diagnóstico" en frontend | Revisado: "hallazgo detectado", "probabilidad estimada", "resultado preliminar" |
| M9 | No había validación automática de pipeline | Tests documentados en Fase 5 (7 tests obligatorios) |
| M10 | Documentación CRISP-DM inexistente | Creados 6 archivos en docs/crisp-dm/ + ml_methodology_review.md |

---

## 4. Decisiones que Dependen del Dataset Real

| Decisión | Estado | Acción Requerida |
|----------|--------|------------------|
| Confirmar 12 clases pulmonares | Pendiente | Ejecutar prepare_dataset.py -> revisar dataset_statistics.csv. Si alguna clase < 50 positivos en TRAIN, documentar y decidir exclusión. |
| Verificar prevalencia Pneumonia | Pendiente | Literatura reporta ~1-2%. Si confirmado muy bajo, evaluar si métricas son fiables. |
| Confirmar patient overlap = 0 | Pendiente | prepare_dataset.py falla si overlap > 0. Ejecutar y confirmar. |
| Detectar imágenes corruptas/duplicadas | Pendiente | dataset_summary.json reportará duplicate_images, invalid_images. |
| Validar splits stratificados | Pendiente | Revisar dataset_statistics.csv -- distribución similar train/val/test. |

---

## 5. Decisiones que Requieren Ejecución Experimental

| Métrica/Resultado | Estado | Nota |
|-------------------|--------|------|
| AUC-ROC por clase | Pendiente | Se genera en metrics.csv tras training.evaluate |
| Sensibilidad/Especificidad/F1 | Pendiente | En metrics.csv y classification_report.json |
| Macro/Micro AUC | Pendiente | En classification_report.json |
| Average Precision (PR-AUC) | Pendiente | En metrics.csv |
| Matrices de confusión | Pendiente | En confusion_matrix.csv + plots |
| Curvas ROC/PR | Pendiente | Generadas con --plot |
| Comparación baseline vs fine-tuned | Pendiente | training.compare -> comparison.json |
| Tiempo entrenamiento (RTX 3050) | Pendiente | Medir en training_history.csv |
| Tiempo inferencia | Pendiente | Medir en logs Celery / ResultadoCNN.tiempo_inferencia_seg |
| Reducción tiempo informes | Pendiente | Estudio separado -- no sale del modelo |

---

## 6. Archivos Modificados en Esta Revisión

### Configuración
- backend/training/config.yaml -- 12 clases, augmentation, pos_weight, thresholds, experiment tracking

### Pipeline de Datos
- backend/training/dataset.py -- Transforms separados train/val/test, augmentation configurable, labels configurables
- backend/training/prepare_dataset.py -- Validación estricta overlap, dataset_statistics.csv, dataset_summary.json, labels configurables

### Entrenamiento
- backend/training/train.py -- pos_weight desde TRAIN, threshold optimization en VAL, CSV logging, checkpoints con metadata completa
- backend/training/model.py -- save_checkpoint/load_checkpoint con thresholds + pos_weight, labels configurables
- backend/training/threshold_optimizer.py -- NUEVO: Optimización Youden's J / F1-max / fixed-sensitivity en VALIDATION only

### Evaluación
- backend/training/evaluate.py -- REESCRITO: Usa thresholds del checkpoint, genera CSV/JSON/plots completos, NO recalcula thresholds

### Inferencia y Integración
- backend/training/inference.py -- NUEVO: Módulo standalone load_model(), predict(), predict_from_file()
- backend/training/experiment_tracker.py -- NUEVO: Gestión experiments/exp_XXX/
- backend/diagnostico/services.py -- REESCRITO: Error explícito si NEORX_MODEL_PATH no existe, thresholds del checkpoint, terminología correcta
- backend/niveles.py -- REESCRITO: Separación thresholds modelo vs niveles visuales, API documentada
- backend/diagnostico/views_niveles.py -- Actualizado para nueva API

### Documentación
- README.training.md -- Eliminadas métricas inventadas, actualizado con salidas reales
- docs/crisp-dm/1_business_understanding.md -- NUEVO
- docs/crisp-dm/2_data_understanding.md -- NUEVO
- docs/crisp-dm/3_data_preparation.md -- NUEVO
- docs/crisp-dm/4_modeling.md -- NUEVO
- docs/crisp-dm/5_evaluation.md -- NUEVO
- docs/crisp-dm/6_deployment.md -- NUEVO
- docs/ml_methodology_review.md -- NUEVO (este archivo)

---

## 7. Próximos Pasos (Orden Obligatorio)

1. Instalar PyTorch CUDA (manual, ver diagnóstico compatibilidad)
2. Descargar NIH manualmente -> data/nih/
3. Ejecutar prepare_dataset.py -> genera splits + estadísticas
4. Verificar dataset_statistics.csv -> confirmar 12 clases viables
5. Ejecutar prueba pipeline --max-samples 2000 (verificar todo fluye)
6. Entrenamiento real training.train (exp_001)
7. Evaluación final training.evaluate (TEST una sola vez)
8. Integración Django -> copiar checkpoint, configurar NEORX_MODEL_PATH
9. Completar documentación CRISP-DM con resultados reales

---

## 8. Declaración de No-Resultados

**Todas las métricas cuantitativas (AUC, sensibilidad, especificidad, F1, precision, recall, AP, tiempos, reducciones) son PENDIENTE DE EJECUCIÓN EXPERIMENTAL.**

No se deben citar, asumir ni inferir valores numéricos de rendimiento hasta que training.evaluate genere metrics.csv y classification_report.json sobre el TEST set real.
