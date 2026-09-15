#!/usr/bin/env bash
# ============================================================
# Neo RX - Fine-tuning Launch Script for RunPod A100
# ============================================================
# Usage:
#   1. Upload this repo to RunPod (or clone via git)
#   2. chmod +x train_on_runpod.sh
#   3. ./train_on_runpod.sh
# ============================================================

set -euo pipefail

# Config
IMAGE_NAME="neorx-training"
DATA_VOLUME="/workspace/data"
CKPT_VOLUME="/workspace/checkpoints"
RUNS_VOLUME="/workspace/runs"

echo "============================================================"
echo "Neo RX Fine-tuning - NIH ChestX-ray14 Subset (15k balanced)"
echo "============================================================"
echo ""

# 1. Build Docker image
echo "[1/5] Building Docker image: $IMAGE_NAME"
docker build -f Dockerfile.training -t "$IMAGE_NAME" .

# 2. Prepare dataset (download CSV + stratified subset ~15k images)
echo "[2/5] Preparing dataset (stratified subset ~15k)..."
docker run --rm --gpus all \
  -v "$DATA_VOLUME":/workspace/data \
  "$IMAGE_NAME" \
  python -m training.prepare_dataset \
    --data-dir /workspace/data/nih \
    --source kaggle \
    --max-samples 15000 \
    --stratify \
    --seed 42

# 3. Train (2-stage: head-only 3ep -> partial unfreeze 7ep)
echo "[3/5] Training model (A100 ~5-6 hours)..."
docker run --rm --gpus all \
  -v "$DATA_VOLUME":/workspace/data \
  -v "$CKPT_VOLUME":/workspace/checkpoints \
  -v "$RUNS_VOLUME":/workspace/runs \
  "$IMAGE_NAME" \
  python -m training.train --config /workspace/training/config.yaml

# 4. Evaluate on test set
echo "[4/5] Evaluating on test set..."
docker run --rm --gpus all \
  -v "$DATA_VOLUME":/workspace/data \
  -v "$CKPT_VOLUME":/workspace/checkpoints \
  "$IMAGE_NAME" \
  python -m training.evaluate \
    --config /workspace/training/config.yaml \
    --checkpoint /workspace/checkpoints/finetuned_resnet50_nih.pt \
    --plot

# 5. Compare vs baseline
echo "[5/5] Comparing vs baseline (torchxrayvision)..."
docker run --rm --gpus all \
  -v "$DATA_VOLUME":/workspace/data \
  -v "$CKPT_VOLUME":/workspace/checkpoints \
  "$IMAGE_NAME" \
  python -m training.compare \
    --config /workspace/training/config.yaml \
    --finetuned-checkpoint /workspace/checkpoints/finetuned_resnet50_nih.pt

echo ""
echo "============================================================"
echo "TRAINING COMPLETE"
echo "============================================================"
echo "Checkpoint: $CKPT_VOLUME/finetuned_resnet50_nih.pt"
echo "Metrics:    $CKPT_VOLUME/metrics.json"
echo "Comparison: $CKPT_VOLUME/comparison.json"
echo "TensorBoard: tensorboard --logdir $RUNS_VOLUME"
echo ""
echo "Next steps:"
echo "  1. Copy checkpoint to backend/diagnostico/models/"
echo "  2. Set NEORX_MODEL_PATH in .env / docker-compose"
echo "  3. Restart Celery worker"
echo "============================================================"