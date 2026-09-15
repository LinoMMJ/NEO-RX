# Neo RX Fine-tuning Pipeline — README

Complete pipeline to fine-tune a ResNet-50 model on **NIH ChestX-ray14** (112,120 frontal chest X-rays, 14 pathologies) and deploy it in the Neo RX Django backend.

## Overview

| Component | Technology |
|-----------|------------|
| Base model | `torchxrayvision` ResNet-50 (`resnet50-res512-all`) |
| Dataset | NIH ChestX-ray14 (14 labels, multi-label) |
| Training | 2-stage: head-only (3 epochs) → partial unfreeze layer3+4 (7 epochs) |
| Loss | `BCEWithLogitsLoss` on raw logits |
| Hardware | GPU cloud (RunPod A100/H100 recommended) |
| Output | `checkpoints/finetuned_resnet50_nih.pt` (loadable by Django) |

## Quick Start

### 1. Environment Setup (RunPod / Local GPU)

**Option A: Docker (recommended for RunPod)**
```bash
# Build image
docker build -f Dockerfile.training -t neorx-training .

# Run interactive with GPU
docker run --gpus all -it \
  -v /host/data:/workspace/data \
  -v /host/checkpoints:/workspace/checkpoints \
  -v /host/runs:/workspace/runs \
  neorx-training bash
```

**Option B: Local / VM (Python 3.10+)**
```bash
cd backend/training
pip install -r requirements.txt
```

### 2. Download & Prepare Dataset

NIH ChestX-ray14 is ~42 GB (images) + CSV. Two options:

**A. Via Kaggle (requires `kaggle.json` with accepted terms)**
```bash
# Inside container or local env
python -m training.prepare_dataset \
  --data-dir data/nih \
  --source kaggle
```
This downloads via `kagglehub`, consolidates all `images_*.zip` into `data/nih/images/`, copies `Data_Entry_2017.csv`, and creates patient-level splits (70/15/15) in `data/nih/splits.json`.

**B. Manual Download (NIH website / academic access)**
1. Download from NIH: https://nihcc.app.box.com/v/ChestXray-NIHCC
2. Extract all `images_*.tar.gz` into `data/nih/images/`
3. Place `Data_Entry_2017.csv` in `data/nih/`
4. Run:
```bash
python -m training.prepare_dataset \
  --data-dir data/nih \
  --source local
```

**Output:**
```
data/nih/
├── images/                 # 112,120 PNG files
├── Data_Entry_2017.csv     # Metadata
├── splits.json             # Train/val/test indices (patient-level)
└── labels.json             # NIH_LABELS list
```

### 3. Train Model

```bash
python -m training.train --config training/config.yaml
```

**Expected timeline on A100 (40GB):**
| Phase | Epochs | Time (est.) |
|-------|--------|-------------|
| Head-only | 3 | ~1.5–2 hours |
| Partial unfreeze | 7 | ~3–4 hours |
| **Total** | **10** | **~5–6 hours** |

**Key config knobs (`training/config.yaml`):**
```yaml
train:
  epochs_head: 3           # Head-only epochs
  epochs_finetune: 7       # Unfreeze epochs
  lr_head: 1.0e-3          # Head learning rate
  lr_finetune: 1.0e-4      # Finetune learning rate
  batch_size: 32           # Adjust for GPU memory
  mixed_precision: true    # Enable AMP
```

**Outputs:**
- `checkpoints/best_epoch*_auc*.pt` — best per-epoch checkpoints
- `checkpoints/finetuned_resnet50_nih.pt` — **final production checkpoint**
- `runs/<timestamp>/` — TensorBoard logs

**Monitor with TensorBoard:**
```bash
tensorboard --logdir runs --port 6006
```

### 4. Evaluate on Test Set

```bash
python -m training.evaluate \
  --config training/config.yaml \
  --checkpoint checkpoints/finetuned_resnet50_nih.pt \
  --plot
```

**Outputs:**
- `checkpoints/metrics.json` — Per-class AUC, sensitivity, specificity, F1, optimal thresholds
- `checkpoints/metrics_auc_curves.png` — ROC curves (if `--plot`)

### 5. Compare with Baseline

```bash
python -m training.compare \
  --config training/config.yaml \
  --finetuned-checkpoint checkpoints/finetuned_resnet50_nih.pt
```

**Output:**
- `checkpoints/comparison.json` — Side-by-side AUC per class + macro average
- Prints comparison table showing delta per pathology

### 6. Deploy to Django Backend

1. **Copy checkpoint** to backend model directory:
```bash
mkdir -p backend/diagnostico/models
cp checkpoints/finetuned_resnet50.pt backend/diagnostico/models/
```

2. **Set environment variable** in Django settings / `.env` / docker-compose:
```bash
# .env or docker-compose.yml environment:
NEORX_MODEL_PATH=/app/diagnostico/models/finetuned_resnet50_nih.pt
```
Or absolute path on host:
```bash
NEORX_MODEL_PATH=/absolute/path/to/backend/diagnostico/models/finetuned_resnet50_nih.pt
```

3. **Restart Celery worker** (and Django if needed):
```bash
docker compose restart celery_worker
# or
systemctl restart neorx-celery
```

4. **Verify integration:**
   - Upload a DICOM via frontend → Escaneo page
   - Check logs: `INFO [CNN TASK ...] Modelo fine-tuned cargado desde ...`
   - Results should show 12 pulmonary pathologies (Cardiomegaly & Hernia excluded)

## Checkpoint Format

The saved `.pt` contains:
```python
{
    "state_dict": ...,           # Full model state (backbone + head + op_norm)
    "pathologies": [...],        # 14 NIH labels in order
    "labels_es": {...},          # EN -> ES mapping
    "num_classes": 14,
    "model_arch": "resnet50",
    "base_weights": "resnet50-res512-all",
    "pulmonary_labels": [...],   # 12 pulmonary-only labels
    "metrics": {...},            # Best validation metrics
    "saved_at": "2026-...Z",
    "extra": {...}               # Config, epoch, phase
}
```

## Integration Details (DetectorTorax)

When `NEORX_MODEL_PATH` is set and valid, `DetectorTorax.cargar()`:
1. Loads checkpoint with `weights_only=False`
2. Instantiates base `xrv.models.ResNet(weights="resnet50-res512-all")`
3. Replaces `model.model.fc = nn.Linear(2048, 14)`
4. Loads `state_dict` (strict=True)
5. Sets `model.pathologies = checkpoint["pathologies"]`
6. In `predecir()`: maps EN→ES using `checkpoint["labels_es"]`, filters to pulmonary-only (excludes Cardiomegaly, Hernia)

**Result:** Frontend receives 12 pathologies with ES names, ordered by probability descending — **zero frontend changes required**.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| OOM on A100 40GB | Reduce `batch_size` to 16 or 8 in config |
| Kaggle download fails | Ensure `kaggle.json` in `~/.kaggle/` with accepted NIH terms |
| `weights_only` error | Checkpoint uses `weights_only=False` (contains lists/dicts) — this is intentional |
| AUC NaN for some classes | Class has no positive/negative samples in test split — normal for rare pathologies |
| Frontend shows 0 pathologies | Check `NEORX_MODEL_PATH` env var, restart Celery, verify checkpoint loads in logs |

## Expected Metrics (Reference)

Based on literature (Quispe & Mamani 2023, Torrez & Condori 2024) and torchxrayvision baseline:

| Pathology | Baseline AUC | Target Finetuned AUC |
|-----------|--------------|---------------------|
| Atelectasis | ~0.82 | >0.85 |
| Cardiomegaly | ~0.91 | >0.92 |
| Consolidation | ~0.79 | >0.83 |
| Edema | ~0.88 | >0.90 |
| Effusion | ~0.86 | >0.89 |
| Pneumonia | ~0.76 | >0.80 |
| Pneumothorax | ~0.84 | >0.87 |
| **Macro Avg** | **~0.82** | **>0.85** |

## License & Citation

- NIH ChestX-ray14: Wang et al., "ChestX-ray8: Hospital-scale Chest X-ray Database", 2017
- torchxrayvision: Cohen et al., "TorchXRayVision", 2022
- This code: Academic use only (Proyecto de Grado Neo RX)

## Support

For issues with the training pipeline, check:
1. TensorBoard logs for loss/AUC curves
2. `metrics.json` for per-class diagnostics
3. Django logs for integration errors (`NEORX_MODEL_PATH` loading)