# Entrenamiento de Neo RX focused3 en Kaggle

> El flujo vigente está documentado en
> [`docs/entrenamiento-focused3.md`](docs/entrenamiento-focused3.md), usa
> `backend/training/config.focused3.kaggle.yaml` y el notebook
> `notebooks/neorx_training_kaggle_focused3.ipynb`. Los flujos focused5 y de
> 12 clases se conservan únicamente como antecedentes reproducibles.

Este pipeline ajusta el ResNet-50 preentrenado de `torchxrayvision` con NIH ChestX-ray14. El flujo está preparado para usar el nivel gratuito de Kaggle, leer las imágenes directamente desde `/kaggle/input` y guardar todo resultado en `/kaggle/working`.

> El modelo es apoyo a la interpretación radiológica. Las métricas reales quedan pendientes hasta ejecutar el entrenamiento completo y evaluar el conjunto de prueba.

## Qué incluye

- Auditoría de imágenes corruptas, ausentes, casi constantes, ambiguas y duplicadas por SHA-256.
- Manifiesto limpio con ruta real, dimensiones, estadísticas de píxel, paciente y proyección AP/PA.
- División determinista 70/15/15 por paciente, sin fuga entre train, validación y prueba.
- Fine-tuning en dos fases: cabeza nueva durante 3 épocas y `layer3`/`layer4` durante 7 épocas.
- `BCEWithLogitsLoss` con `pos_weight` calculado exclusivamente en train.
- AMP, recorte de gradiente, early stopping y umbrales optimizados exclusivamente en validación.
- `last.pt` reanudable y `best.pt` guardados atómicamente después de cada época.
- Evaluación final global y por proyección AP/PA.

## Inicio rápido en Kaggle

1. Crea un Notebook privado en Kaggle.
2. En **Add Input**, adjunta un dataset que contenga `Data_Entry_2017.csv` y todas las imágenes de NIH ChestX-ray14.
3. En **Notebook options**, activa Internet y selecciona un acelerador GPU disponible.
4. Importa [`notebooks/neorx_training_kaggle_focused3.ipynb`](notebooks/neorx_training_kaggle_focused3.ipynb).
5. Ejecuta todas las celdas. Este cuaderno no permite `--max-samples` para evitar publicar otro checkpoint piloto.
6. Guarda una versión con outputs y descarga checkpoints, manifiestos, resultados y runs de `focused3`.

Kaggle puede cambiar el tipo de GPU gratuito disponible y sus límites de sesión. El cuaderno detecta la GPU en lugar de depender de un modelo específico.

## Comandos equivalentes

Desde `backend/`, con el dataset ya adjunto:

```bash
python -m pip install -r training/requirements.kaggle.txt
python -m training.validate_dataset \
  --input-root /kaggle/input/nih-chest-xrays \
  --output-dir /kaggle/working/manifests-focused3 \
  --workers 4
python -m training.create_splits \
  --manifest /kaggle/working/manifests-focused3/clean_manifest.csv \
  --output-dir /kaggle/working/manifests-focused3 \
  --config /kaggle/working/config.focused3.runtime.yaml \
  --seed 42
python -m training.train \
  --config /kaggle/working/config.focused3.runtime.yaml \
  --device cuda
```

El perfil focused3 rechaza `--max-samples`; el checkpoint de integración debe provenir del conjunto completo.

## Reanudar una sesión interrumpida

Publica o adjunta como Dataset privado los outputs de la sesión anterior y apunta a `last.pt`:

```bash
python -m training.train \
  --config /kaggle/working/config.focused3.runtime.yaml \
  --device cuda \
  --resume /kaggle/input/neorx-focused3-checkpoints/last.pt
```

El checkpoint conserva modelo, optimizador, scheduler, AMP, generadores aleatorios, fase, próxima época, paciencia y mejor AUC. Conserva también `best.pt`; el entrenador lo copia junto al nuevo output cuando reanuda desde otra entrada.

No mezcles checkpoints del piloto con el entrenamiento completo. Empieza el completo en una salida limpia.

## Evaluación final

```bash
python -m training.evaluate \
  --config /kaggle/working/config.focused3.runtime.yaml \
  --checkpoint /kaggle/working/checkpoints-focused3/neorx_focused3_resnet50.pt \
  --device cuda \
  --output-dir /kaggle/working/results-focused3 \
  --plot
```

Resultados principales:

- `metrics.csv`: AUC, AP, sensibilidad, especificidad, precisión y F1 por clase.
- `metrics_by_view.csv`: las mismas métricas separadas por AP/PA.
- `thresholds.csv`: umbrales aprendidos con validación.
- `classification_report.json` y `confusion_matrix.csv`.
- Curvas ROC/PR y matrices de confusión.

## Integración con Django

Copia `neorx_focused3_resnet50.pt` fuera del repositorio y configura:

```env
NEORX_MODEL_PATH=/ruta/segura/neorx_focused3_resnet50.pt
```

Reinicia Django y el worker de Celery. El repositorio ignora `.pt`, datasets y outputs para evitar subir archivos grandes o datos clínicos a Git.

## Reglas de validez

- No ajustes umbrales con test.
- No reportes métricas del piloto.
- Conserva `dataset_audit.json`, `split_summary.json`, configuración, historial y checkpoint para reproducibilidad.
- Si una clase no tiene positivos en alguno de los tres conjuntos, `create_splits.py` falla y obliga a revisar el dataset.
- Verifica que `patient_overlap` sea `0` antes de entrenar.
- Registra la GPU y la versión de PyTorch impresas por el Notebook.

## Formato del checkpoint

El `.pt` final contiene los pesos, las tres clases, traducciones, umbrales, política de abstención, `pos_weight`, configuración y métricas. `last.pt` añade el estado completo necesario para reanudar.

## Entrenamiento nocturno listo para Kaggle

Usar `entrega_kaggle/NeoRX_Entrenamiento_Nocturno.ipynb`, adjuntar `entrega_kaggle/neorx_kaggle_entrenamiento.zip` como Dataset privado y el NIH completo. La guía paso a paso está en [docs/GUIA_KAGGLE_NOCTURNO.md](docs/GUIA_KAGGLE_NOCTURNO.md).

Primero ejecutar el modo `train` con Save Version / Save & Run All. Si el presupuesto de tiempo se agota, reanudar desde la salida completa anterior; ejecutar `evaluate` solo cuando termine. La preparación no lanza ni publica nada en la cuenta de Kaggle y mantiene el modelo local actual.

Para reconstruir el paquete después de modificar el código: `python scripts/build_kaggle_bundle.py`. El empaquetado usa una lista explícita de archivos y no incluye `.env`, base de datos ni imágenes clínicas. Las pruebas de reanudación usan datos sintéticos; el rendimiento diagnóstico queda pendiente del experimento.
