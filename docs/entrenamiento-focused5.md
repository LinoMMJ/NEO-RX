# Neo RX focused-v2: entrenamiento de cinco hallazgos

## Objetivo

Esta versión reduce el alcance del modelo a cinco hallazgos radiográficos:

- Emphysema — Enfisema
- Edema — Edema pulmonar
- Effusion — Derrame pleural
- Mass — Masa pulmonar
- Pneumothorax — Neumotórax

La selección es una hipótesis experimental basada en la separación observada en el
checkpoint anterior. No constituye validación clínica. `Mass` puede retirarse para
probar cuatro clases editando `target_labels`, `labels_es` y `model.num_classes`.

El problema continúa siendo **multietiqueta**. Una radiografía puede contener más de
un hallazgo real; el entrenamiento no usa softmax ni fuerza un único diagnóstico.
La reducción de ambigüedad se consigue mediante menos objetivos, ejemplos negativos
difíciles y umbrales que priorizan precisión.

## Diferencias frente al modelo de 12 clases

- Las etiquetas se leen de `target_labels`; ya no están acopladas a una constante de 12 clases.
- La configuración falla si `model.num_classes` no coincide con las etiquetas.
- Las divisiones continúan siendo por paciente y permiten exigir un mínimo de positivos por clase.
- El mejor checkpoint se escoge por macro average precision (PR-AUC), más informativa con clases poco frecuentes.
- Los umbrales de validación buscan precisión mínima de 0,85 y luego maximizan recall.
- Si validación no alcanza esa precisión, se usa el umbral conservador máximo y queda registrado en `thresholds_validation.csv`.
- La evaluación produce `decision_summary.json` con detecciones múltiples y falsos positivos por imagen.

Las imágenes con patologías NIH no seleccionadas permanecen como negativos difíciles
para los cinco objetivos. No deben describirse como “radiografías sanas”. `No Finding`
solo conserva el significado original del dataset NIH.

## Ejecución en Kaggle

Importar `notebooks/neorx_training_kaggle_focused5.ipynb`, adjuntar NIH ChestX-ray14
y activar GPU. Primero ejecutar `MODE = "pilot"`; sus métricas no son publicables.
Después iniciar una salida limpia y ejecutar `MODE = "full"`.

Comandos equivalentes desde `backend/`:

```bash
python -m training.validate_dataset \
  --input-root /kaggle/input/nih-chest-xrays \
  --output-dir /kaggle/working/manifests-focused5 \
  --workers 4

python -m training.create_splits \
  --manifest /kaggle/working/manifests-focused5/clean_manifest.csv \
  --output-dir /kaggle/working/manifests-focused5 \
  --config training/config.focused5.kaggle.yaml \
  --min-positives-per-label 25 \
  --seed 42

python -m training.train \
  --config training/config.focused5.kaggle.yaml \
  --device cuda

python -m training.evaluate \
  --config training/config.focused5.kaggle.yaml \
  --checkpoint /kaggle/working/checkpoints-focused5/neorx_focused5_resnet50.pt \
  --device cuda \
  --output-dir /kaggle/working/results-focused5 \
  --plot
```

## Criterios antes de reemplazar el modelo actual

No desplegar únicamente porque el macro AUC aumente. Revisar en test independiente:

1. Precisión, sensibilidad, PR-AUC y matriz de confusión de cada clase.
2. `mean_false_positive_labels_per_image`.
3. `multiple_detection_rate` frente al modelo anterior.
4. Resultados separados por proyección AP y PA.
5. Errores revisados por un profesional y prueba externa fuera de NIH.

El objetivo de precisión 0,85 se selecciona en validación; no garantiza 0,85 en test
ni en radiografías de la clínica. El conjunto test se consulta una sola vez al cerrar
la configuración, sin reajustar umbrales con sus resultados.
