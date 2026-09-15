<# 
.SYNOPSIS
    Neo RX - Fine-tuning Launch Script for RunPod A100 (PowerShell)

.DESCRIPTION
    Runs the complete fine-tuning pipeline on RunPod:
    1. Build Docker image
    2. Prepare NIH subset (stratified 15k images)
    3. Train (2-stage: head-only + partial unfreeze)
    4. Evaluate on test set
    5. Compare vs baseline

.PREREQUISITES
    - RunPod instance with A100 GPU
    - Docker installed
    - kaggle.json with NIH ChestX-ray14 consent in ~/.kaggle/
    - This repo cloned on the instance

.USAGE
    # On RunPod (PowerShell):
    .\train_on_runpod.ps1
#>

param(
    [string]$ImageName = "neorx-training",
    [string]$DataVolume = "/workspace/data",
    [string]$CkptVolume = "/workspace/checkpoints",
    [string]$RunsVolume = "/workspace/runs"
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "Neo RX Fine-tuning - NIH ChestX-ray14 Subset (15k balanced)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Build Docker image
Write-Host "[1/5] Building Docker image: $ImageName" -ForegroundColor Yellow
docker build -f Dockerfile.training -t $ImageName .

# 2. Prepare dataset
Write-Host "[2/5] Preparing dataset (stratified subset ~15k)..." -ForegroundColor Yellow
docker run --rm --gpus all `
  -v "$DataVolume:/workspace/data" `
  $ImageName `
  python -m training.prepare_dataset `
    --data-dir /workspace/data/nih `
    --source kaggle `
    --max-samples 15000 `
    --stratify `
    --seed 42

# 3. Train
Write-Host "[3/5] Training model (A100 ~5-6 hours)..." -ForegroundColor Yellow
docker run --rm --gpus all `
  -v "$DataVolume:/workspace/data" `
  -v "$CkptVolume:/workspace/checkpoints" `
  -v "$RunsVolume:/workspace/runs" `
  $ImageName `
  python -m training.train --config /workspace/training/config.yaml

# 4. Evaluate
Write-Host "[4/5] Evaluating on test set..." -ForegroundColor Yellow
docker run --rm --gpus all `
  -v "$DataVolume:/workspace/data" `
  -v "$CkptVolume:/workspace/checkpoints" `
  $ImageName `
  python -m training.evaluate `
    --config /workspace/training/config.yaml `
    --checkpoint /workspace/checkpoints/finetuned_resnet50_nih.pt `
    --plot

# 5. Compare
Write-Host "[5/5] Comparing vs baseline (torchxrayvision)..." -ForegroundColor Yellow
docker run --rm --gpus all `
  -v "$DataVolume:/workspace/data" `
  -v "$CkptVolume:/workspace/checkpoints" `
  $ImageName `
  python -m training.compare `
    --config /workspace/training/config.yaml `
    --finetuned-checkpoint /workspace/checkpoints/finetuned_resnet50_nih.pt

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "TRAINING COMPLETE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Checkpoint: $CkptVolume/finetuned_resnet50_nih.pt" -ForegroundColor Cyan
Write-Host "Metrics:    $CkptVolume/metrics.json" -ForegroundColor Cyan
Write-Host "Comparison: $CkptVolume/comparison.json" -ForegroundColor Cyan
Write-Host "TensorBoard: tensorboard --logdir $RunsVolume" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Copy checkpoint to backend/diagnostico/models/"
Write-Host "  2. Set NEORX_MODEL_PATH in .env / docker-compose"
Write-Host "  3. Restart Celery worker"
Write-Host "============================================================" -ForegroundColor Green