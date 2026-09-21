# CRISP-DM Fase 4: Modelado (Modeling)

## Arquitectura del Modelo

| Componente | Especificación |
|------------|----------------|
| **Base** | `torchxrayvision` ResNet-50 (`resnet50-res512-all`) |
| **Pesos iniciales** | Preentrenados en 5 datasets (NIH, RSNA, SIIM, VinBigData, PC) |
| **Arquitectura** | ResNet-50 estándar (conv1, bn1, layer1-4, fc) |
| **Clases de salida** | 12 (patologías pulmonares) |
| **Activación final** | Sigmoid (via `op_norm` en xrv) — multi-label |
| **Pérdida** | `BCEWithLogitsLoss` (logits raw, no probabilidades) |

## Transfer Learning: Estrategia de 2 Fases

### Fase 1: Head-Only (Epochs 1-3)
```python
# Congelar TODO excepto fc nueva
for param in model.parameters():
    param.requires_grad = False
for param in model.model.fc.parameters():
    param.requires_grad = True

# Optimizer: AdamW lr=1e-3, weight_decay=1e-4
```

### Fase 2: Partial Unfreeze (Epochs 4-10)
```python
# Descongelar layer3, layer4, fc
for name, param in model.model.named_parameters():
    if "layer3" in name or "layer4" in name or "fc" in name:
        param.requires_grad = True
    else:
        param.requires_grad = False

# Optimizer: AdamW lr=1e-4, weight_decay=1e-4
```

## Configuración de Entrenamiento

| Parámetro | Valor | Justificación |
|-----------|-------|---------------|
| `batch_size` | 32 (ajustable por VRAM) | Balance memoria/estabilidad |
| `epochs_head` | 3 | Convergencia rápida de head |
| `epochs_finetune` | 7 | Fine-tuning conservador |
| `lr_head` | 1e-3 | Head nuevo necesita LR mayor |
| `lr_finetune` | 1e-4 | Backbone preentrenado, LR bajo |
| `weight_decay` | 1e-4 | Regularización L2 |
| `mixed_precision` | True | Ahorro VRAM, velocidad |
| `grad_clip` | 1.0 | Estabilidad gradientes |
| `early_stopping_patience` | 4 | Evita overfitting |
| `scheduler` | ReduceLROnPlateau(factor=0.5, patience=2) | Adaptativo |

## Manejo de Desbalance: pos_weight

```python
# Calculado EXCLUSIVAMENTE desde TRAIN split
pos_weight[c] = n_neg[c] / n_pos[c]  # por clase

# BCEWithLogitsLoss(pos_weight=pos_weight)
```

## Optimización de Thresholds (VALIDATION Only)

```python
# Youden's J = Sensitivity + Specificity - 1
# Para cada clase, threshold que maximiza J en VALIDATION
# Guardado en checkpoint: checkpoint["thresholds"]
```

## Métricas de Selección de Checkpoint

- **Métrica principal**: Macro AUC-ROC en VALIDATION
- **Early stopping**: Si no mejora macro AUC por 4 epochs
- **Best checkpoint**: Mejor macro AUC global (head + finetune)

## Logging y Reproducibilidad

| Artefacto | Ubicación | Contenido |
|-----------|-----------|-----------|
| TensorBoard | `runs/<timestamp>/` | Loss, AUC por epoch/clase |
| CSV History | `runs/<timestamp>/training_history.csv` | Epoch, phase, loss, AUCs, LR |
| Checkpoints | `checkpoints/` | Pesos + metadata + thresholds |
| Best epoch | `checkpoints/best_epoch*_auc*.pt` | Por epoch |
| Final | `checkpoints/finetuned_resnet50_nih.pt` | Producción |

## Configuración de Seeds (Reproducibilidad)

```python
seed = 42
random.seed(seed)
np.random.seed(seed)
torch.manual_seed(seed)
torch.cuda.manual_seed_all(seed)
torch.backends.cudnn.deterministic = True
torch.backends.cudnn.benchmark = False
```

## Experimentos (Tracking)

Estructura:
```
experiments/
└── exp_001_YYYYMMDD_HHMMSS/
    ├── config.yaml          # Config completa usada
    ├── checkpoints/         # Checkpoints del experimento
    ├── logs/                # TensorBoard logs
    └── results/             # Evaluación final
        ├── metrics.csv
        ├── thresholds.csv
        ├── classification_report.json
        └── confusion_matrix.csv
```

**IMPORTANTE**: Solo crear `exp_001` tras primera ejecución real. No pre-crear experimentos ficticios.

## Entregables de esta Fase

- [ ] Modelo entrenado (checkpoint final con thresholds + pos_weight)
- [ ] `training_history.csv` con todos los epochs
- [ ] TensorBoard logs completos
- [ ] Configuración exacta usada (config.yaml copiado a experimento)
- [ ] Documentación de decisiones: por qué 2 fases, por qué lr, por qué unfreeze layer3/4
