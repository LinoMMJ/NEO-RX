# CRISP-DM Fase 5: Evaluación (Evaluation)

## Principio Fundamental: Separación Estricta

```
TRAIN (70%)     → Aprendizaje de parámetros
VALIDATION (15%) → Selección de modelo + Thresholds + Early stopping
TEST (15%)      → Evaluación FINAL una sola vez
```

**NUNCA** usar TEST para:
- Seleccionar threshold
- Seleccionar modelo/checkpoint
- Decidir epochs / early stopping
- Ajustar hiperparámetros
- Seleccionar arquitectura

## Evaluación Final (Sobre TEST Set)

### Ejecución
```bash
python -m training.evaluate \
  --config training/config.yaml \
  --checkpoint checkpoints/finetuned_resnet50_nih.pt \
  --plot
```

### Usa Thresholds del Checkpoint (VALIDATION)

```python
# Cargar thresholds optimizados en VALIDATION
thresholds = checkpoint["thresholds"]  # Dict {label: threshold}

# En TEST: solo aplicar thresholds, NO recalcular
preds = (probs >= threshold).astype(int)
```

## Métricas Calculadas (Por Clase)

| Métrica | Fórmula | Uso |
|---------|---------|-----|
| **AUC-ROC** | `roc_auc_score(y_true, y_scores)` | Discriminación global |
| **Average Precision (PR-AUC)** | `average_precision_score(y_true, y_scores)` | Desbalance severo |
| **Sensibilidad (Recall)** | TP / (TP + FN) | Detección de positivos |
| **Especificidad** | TN / (TN + FP) | Evitar falsos positivos |
| **Precisión** | TP / (TP + FP) | Confianza en detección |
| **F1-Score** | 2·P·R / (P + R) | Balance P/R |
| **Threshold** | Del checkpoint (Youden's J en VAL) | Decisión binaria |

## Promedios Globales (Multi-label)

| Promedio | Descripción |
|----------|-------------|
| **Macro AUC** | Promedio AUC por clase (peso igual por clase) |
| **Micro AUC** | AUC global concatenando todas las predicciones |
| **Macro AP** | Promedio Average Precision por clase |
| **Micro AP** | AP global |

## Archivos de Salida Generados

| Archivo | Contenido |
|---------|-----------|
| `metrics.csv` | Por clase: AUC, AP, Sens, Spec, Prec, F1, threshold, n_pos, n_neg |
| `thresholds.csv` | `class, threshold` (del checkpoint) |
| `classification_report.json` | JSON completo con todas las métricas + metadata |
| `confusion_matrix.csv` | `class, tn, fp, fn, tp` (binario one-vs-rest) |
| `roc_curves.png` | Curvas ROC por clase (si `--plot`) |
| `pr_curves.png` | Curvas Precision-Recall por clase (si `--plot`) |
| `confusion_matrices.png` | Heatmaps matriz confusión por clase (si `--plot`) |

## Matriz de Confusión (Multi-label)

Para clasificación multi-label, se generan **matrices binarias one-vs-rest por etiqueta**:

```
Para cada clase c:
                 Predicho Neg    Predicho Pos
Real Neg            TN              FP
Real Pos            FN              TP
```

**NO** es una matriz de confusión multi-clase tradicional (eso sería para single-label).

## Comparación con Baseline

```bash
python -m training.compare \
  --config training/config.yaml \
  --finetuned-checkpoint checkpoints/finetuned_resnet50_nih.pt
```

- Evalúa **ambos modelos en el MISMO test set**
- Baseline usa sus propios thresholds (0.5 default o calibrados propios)
- Fine-tuned usa thresholds de su checkpoint (VALIDATION)
- Reporte: `comparison.json` + tabla por clase con delta AUC

## Casos Edge (Documentar en Tesis)

| Situación | Manejo |
|-----------|--------|
| Clase sin positivos en TEST | AUC = NaN, métricas = NaN, documentar |
| Clase sin negativos en TEST | AUC = NaN, métricas = NaN, documentar |
| Threshold = 0.5 (default) | Indicar que no hubo optimización válida |
| AUC < 0.5 | Modelo peor que azar — investigar |

## Validación Metodológica (Tests Automatizados)

El pipeline incluye validaciones que DEBEN pasar:

```python
# Test 1: Patient overlap = 0
assert len(train_patients & val_patients) == 0
assert len(train_patients & test_patients) == 0
assert len(val_patients & test_patients) == 0

# Test 2: TRAIN tiene augmentation, VAL/TEST no
assert train_dataset.transform.has_augmentation()
assert not val_dataset.transform.has_augmentation()
assert not test_dataset.transform.has_augmentation()

# Test 3: Threshold NO se calcula en TEST
# (evaluate.py usa checkpoint["thresholds"])

# Test 4: pos_weight solo usa TRAIN
# (train.py calcula desde train_loader)

# Test 5: Checkpoint contiene thresholds
assert "thresholds" in checkpoint

# Test 6: Inference carga checkpoint correctamente
model = load_model(checkpoint_path)
result = predict(model, image)

# Test 7: NEORX_MODEL_PATH no existe → ERROR (no fallback)
```

## Entregables de esta Fase

- [ ] `metrics.csv` con todas las métricas por clase
- [ ] `thresholds.csv` con thresholds usados (del checkpoint)
- [ ] `classification_report.json` completo
- [ ] `confusion_matrix.csv` matrices binarias
- [ ] Gráficos: ROC, PR, Confusion matrices
- [ ] `comparison.json` baseline vs fine-tuned
- [ ] Documentación de casos edge (clases con NaN)
- [ ] Confirmación: TEST usado UNA SOLA VEZ
