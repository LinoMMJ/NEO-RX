# Entrenamiento de Neo RX V1.3.7 en Kaggle

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
4. Importa [`notebooks/neorx_training_kaggle.ipynb`](notebooks/neorx_training_kaggle.ipynb).
5. Ejecuta las celdas en orden con `MODE = "pilot"`.
6. Si el piloto termina y genera `last.pt`, inicia una sesión limpia, cambia a `MODE = "full"` y ejecuta todo otra vez.
7. Guarda una versión del Notebook con sus outputs y descarga `neorx-v1.3.7-checkpoints.zip`, `manifests/`, `results/` y `runs/`.

Kaggle puede cambiar el tipo de GPU gratuito disponible y sus límites de sesión. El cuaderno detecta la GPU en lugar de depender de un modelo específico.

## Comandos equivalentes

Desde `backend/`, con el dataset ya adjunto:

```bash
python -m pip install -r training/requirements.kaggle.txt
python -m training.validate_dataset \
  --input-root /kaggle/input/nih-chest-xrays \
  --output-dir /kaggle/working/manifests \
  --workers 4
python -m training.create_splits \
  --manifest /kaggle/working/manifests/clean_manifest.csv \
  --output-dir /kaggle/working/manifests \
  --labels pulmonary \
  --seed 42
python -m training.train \
  --config /kaggle/working/config.kaggle.runtime.yaml \
  --device cuda \
  --max-samples 2000
```

`--max-samples 2000` es solamente un smoke test. No uses sus métricas como resultado del proyecto. Para el entrenamiento final ejecuta sin ese argumento.

## Reanudar una sesión interrumpida

Publica o adjunta como Dataset privado los outputs de la sesión anterior y apunta a `last.pt`:

```bash
python -m training.train \
  --config /kaggle/working/config.kaggle.runtime.yaml \
  --device cuda \
  --resume /kaggle/input/neorx-checkpoints/last.pt
```

El checkpoint conserva modelo, optimizador, scheduler, AMP, generadores aleatorios, fase, próxima época, paciencia y mejor AUC. Conserva también `best.pt`; el entrenador lo copia junto al nuevo output cuando reanuda desde otra entrada.

No mezcles checkpoints del piloto con el entrenamiento completo. Empieza el completo en una salida limpia.

## Evaluación final

```bash
python -m training.evaluate \
  --config /kaggle/working/config.kaggle.runtime.yaml \
  --checkpoint /kaggle/working/checkpoints/finetuned_resnet50_nih.pt \
  --device cuda \
  --output-dir /kaggle/working/results \
  --plot
```

Resultados principales:

- `metrics.csv`: AUC, AP, sensibilidad, especificidad, precisión y F1 por clase.
- `metrics_by_view.csv`: las mismas métricas separadas por AP/PA.
- `thresholds.csv`: umbrales aprendidos con validación.
- `classification_report.json` y `confusion_matrix.csv`.
- Curvas ROC/PR y matrices de confusión.

## Integración con Django

Copia `finetuned_resnet50_nih.pt` fuera del repositorio y configura:

```env
NEORX_MODEL_PATH=/ruta/segura/finetuned_resnet50_nih.pt
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

El `.pt` final contiene los pesos, orden de las 12 patologías pulmonares, traducciones, umbrales de validación, `pos_weight`, configuración y métricas. `last.pt` añade el estado completo necesario para reanudar.
