# Entrenamiento focused3 con abstención segura

## Alcance

La versión focused3 evalúa únicamente tres hallazgos radiográficos independientes:

1. Neumotórax (`Pneumothorax`).
2. Derrame pleural (`Effusion`).
3. Edema pulmonar (`Edema`).

Continúa siendo multietiqueta porque los hallazgos pueden coexistir. La ausencia
de una detección no equivale a una radiografía normal.

## Estrategia

- ResNet-50 preentrenada con `torchxrayvision` como inicialización.
- Fine-tuning con todos los datos asignados a entrenamiento; el perfil final
  rechaza `--max-samples`.
- División por paciente y umbrales seleccionados solo con validación.
- Selección del checkpoint mediante macro average precision.
- Cada clase debe alcanzar simultáneamente precisión mínima, sensibilidad mínima
  y soporte suficiente. Si no lo logra queda deshabilitada y el sistema se abstiene.
- Test independiente sin recalcular umbrales.

Los valores iniciales del perfil son precisión ≥ 0,90, sensibilidad ≥ 0,60,
30 predicciones positivas y 100 positivos reales en validación. Son criterios
predefinidos, no una promesa de rendimiento. Si no se cumplen, no deben relajarse
después de mirar test; corresponde mejorar datos o entrenamiento.

## Kaggle

1. Crear un notebook privado y adjuntar NIH ChestX-ray14 completo.
2. Activar GPU e Internet.
3. Importar `notebooks/neorx_training_kaggle_focused3.ipynb`.
4. Ejecutar todas las celdas sin agregar `--max-samples`.
5. Verificar `patient_overlap: 0` en `split_summary.json`.
6. Revisar `thresholds_validation.csv`: las tres filas deben tener
   `enabled=true`; si una aparece deshabilitada, no está lista para decisiones.
7. Ejecutar la evaluación final del notebook sobre test.
8. Conservar `metrics.csv`, `metrics_by_view.csv`, `decision_summary.json`,
   `classification_report.json`, manifiestos, runs y checkpoints.

## Criterios de aceptación

- Evaluación sobre las 16 mil imágenes aproximadas del test completo, no cientos.
- Precisión y sensibilidad por clase reportadas con los umbrales congelados.
- Resultados separados para proyección AP y PA.
- Tasa de múltiples detecciones y falsos positivos por imagen documentadas.
- Revisión manual de errores y, antes de cualquier uso clínico, validación externa
  con etiquetas adjudicadas por profesionales.

## Integración

Copiar `neorx_focused3_resnet50.pt` a `backend/models/` y cambiar la variable:

```env
NEORX_MODEL_PATH=./models/neorx_focused3_resnet50.pt
NEORX_INPUT_SIZE=512
```

Reiniciar Django y Celery. La API leerá del checkpoint las clases, umbrales y
política de decisión. Si falta esa política, devolverá
`modelo_pendiente_validacion` y no transformará scores en hallazgos.
