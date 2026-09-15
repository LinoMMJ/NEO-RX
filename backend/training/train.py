"""
Training Loop for Fine-tuning on NIH ChestX-ray14

Two-stage training:
  1. Head-only (epochs 1-N): only fc layer trainable
  2. Partial unfreeze (epochs N+1-M): layer3, layer4, fc trainable

Uses BCEWithLogitsLoss on raw logits (model.model(x)), NOT xrv forward (which applies sigmoid).
Mixed precision, gradient clipping, early stopping, TensorBoard logging.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import torch
import torch.nn as nn
import torch.optim as optim
import yaml
from torch.cuda.amp import GradScaler, autocast
from torch.utils.tensorboard import SummaryWriter

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset import get_dataloaders, NIH_LABELS
from training.model import (
    build_model,
    count_trainable_params,
    load_checkpoint,
    save_checkpoint,
    set_head_only,
    unfreeze_partial,
)


def parse_args():
    parser = argparse.ArgumentParser(description="Fine-tune ResNet-50 on NIH ChestX-ray14")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("training/config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--resume",
        type=Path,
        default=None,
        help="Path to checkpoint to resume from",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device to use (default: auto)",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_device(device_arg: str) -> torch.device:
    if device_arg == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_arg)


def set_seed(seed: int) -> None:
    import random
    import numpy as np

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def compute_auc_scores(targets: torch.Tensor, probs: torch.Tensor) -> Tuple[List[float], float]:
    """Compute per-class AUC-ROC and macro average."""
    try:
        from sklearn.metrics import roc_auc_score
    except ImportError:
        return [0.0] * targets.shape[1], 0.0

    aucs = []
    for i in range(targets.shape[1]):
        if targets[:, i].sum() == 0 or targets[:, i].sum() == len(targets):
            aucs.append(float("nan"))
        else:
            aucs.append(roc_auc_score(targets[:, i].cpu().numpy(), probs[:, i].cpu().numpy()))
    valid = [a for a in aucs if not (isinstance(a, float) and a != a)]  # filter NaN
    macro = sum(valid) / len(valid) if valid else 0.0
    return aucs, macro


def validate(model: nn.Module, loader, device: torch.device, use_amp: bool) -> Tuple[float, List[float], float]:
    """Run validation, return (loss, per_class_aucs, macro_auc)."""
    model.eval()
    criterion = nn.BCEWithLogitsLoss()

    all_targets = []
    all_logits = []
    total_loss = 0.0
    n_batches = 0

    with torch.no_grad():
        for images, targets, _ in loader:
            images = images.to(device, non_blocking=True)
            targets = targets.to(device, non_blocking=True)

            if use_amp and device.type == "cuda":
                with autocast():
                    logits = model.model(images)
                    loss = criterion(logits, targets)
            else:
                logits = model.model(images)
                loss = criterion(logits, targets)

            total_loss += loss.item()
            n_batches += 1

            all_targets.append(targets.cpu())
            all_logits.append(logits.cpu())

    all_targets = torch.cat(all_targets, dim=0)
    all_logits = torch.cat(all_logits, dim=0)
    all_probs = torch.sigmoid(all_logits)

    avg_loss = total_loss / max(1, n_batches)
    aucs, macro_auc = compute_auc_scores(all_targets, all_probs)

    return avg_loss, aucs, macro_auc


def train_one_epoch(
    model: nn.Module,
    loader,
    optimizer: optim.Optimizer,
    criterion: nn.Module,
    device: torch.device,
    use_amp: bool,
    scaler: GradScaler,
    grad_clip: float,
    epoch: int,
    writer: SummaryWriter,
) -> float:
    """Train one epoch, return average loss."""
    model.train()
    total_loss = 0.0
    n_batches = 0

    for batch_idx, (images, targets, _) in enumerate(loader):
        images = images.to(device, non_blocking=True)
        targets = targets.to(device, non_blocking=True)

        optimizer.zero_grad(set_to_none=True)

        if use_amp and device.type == "cuda":
            with autocast():
                logits = model.model(images)
                loss = criterion(logits, targets)
            scaler.scale(loss).backward()
            if grad_clip > 0:
                scaler.unscale_(optimizer)
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            scaler.step(optimizer)
            scaler.update()
        else:
            logits = model.model(images)
            loss = criterion(logits, targets)
            loss.backward()
            if grad_clip > 0:
                nn.utils.clip_grad_norm_(model.parameters(), grad_clip)
            optimizer.step()

        total_loss += loss.item()
        n_batches += 1

        # Log batch loss
        global_step = epoch * len(loader) + batch_idx
        writer.add_scalar("train/batch_loss", loss.item(), global_step)

    return total_loss / max(1, n_batches)


def main():
    args = parse_args()
    cfg = load_config(args.config)

    # Setup
    device = get_device(args.device)
    set_seed(cfg["train"]["seed"])

    print(f"Device: {device}")
    print(f"Config: {args.config}")

    # DataLoaders
    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    train_loader, val_loader, _ = get_dataloaders(cfg, splits_json, data_dir)

    # Model
    model = build_model(cfg).to(device)
    trainable, total = count_trainable_params(model)
    print(f"Model parameters: {trainable:,} trainable / {total:,} total")

    # Loss & Optimizer
    criterion = nn.BCEWithLogitsLoss()
    use_amp = cfg["train"]["mixed_precision"] and device.type == "cuda"
    scaler = GradScaler() if use_amp else None

    # TensorBoard
    log_dir = Path(cfg["train"]["log_dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=log_dir / datetime.now().strftime("%Y%m%d-%H%M%S"))

    # Resume logic
    start_epoch = 0
    best_macro_auc = 0.0
    patience_counter = 0
    best_checkpoint_path = None

    if args.resume and args.resume.exists():
        print(f"Resuming from {args.resume}")
        ckpt = load_checkpoint(args.resume)
        model.load_state_dict(ckpt["state_dict"], strict=True)
        if "extra" in ckpt and "epoch" in ckpt["extra"]:
            start_epoch = ckpt["extra"]["epoch"] + 1
        if "metrics" in ckpt and "macro_auc" in ckpt["metrics"]:
            best_macro_auc = ckpt["metrics"]["macro_auc"]
        print(f"Resumed at epoch {start_epoch}, best macro AUC: {best_macro_auc:.4f}")

    # ==================== PHASE 1: Head-only ====================
    print(f"\n{'='*60}")
    print(f"PHASE 1: Head-only training ({cfg['train']['epochs_head']} epochs)")
    print(f"{'='*60}")
    set_head_only(model, freeze=True)
    trainable, _ = count_trainable_params(model)
    print(f"Trainable params: {trainable:,}")

    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg["train"]["lr_head"],
        weight_decay=cfg["train"]["weight_decay"],
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=2, verbose=True
    )

    for epoch in range(start_epoch, cfg["train"]["epochs_head"]):
        epoch_start = time.time()

        train_loss = train_one_epoch(
            model, train_loader, optimizer, criterion, device, use_amp, scaler,
            cfg["train"]["grad_clip"], epoch, writer
        )

        val_loss, val_aucs, val_macro_auc = validate(model, val_loader, device, use_amp)
        epoch_time = time.time() - epoch_start

        # Logging
        writer.add_scalar("train/epoch_loss", train_loss, epoch)
        writer.add_scalar("val/epoch_loss", val_loss, epoch)
        writer.add_scalar("val/macro_auc", val_macro_auc, epoch)
        for i, auc in enumerate(val_aucs):
            if not (isinstance(auc, float) and auc != auc):
                writer.add_scalar(f"val/auc_{NIH_LABELS[i]}", auc, epoch)

        # Print progress
        auc_str = " | ".join(
            f"{NIH_LABELS[i]}: {auc:.4f}" if not (isinstance(auc, float) and auc != auc) else f"{NIH_LABELS[i]}: NaN"
            for i, auc in enumerate(val_aucs)
        )
        print(
            f"Epoch {epoch:3d}/{cfg['train']['epochs_head']-1} | "
            f"train_loss: {train_loss:.4f} | val_loss: {val_loss:.4f} | "
            f"macro_AUC: {val_macro_auc:.4f} | time: {epoch_time:.1f}s"
        )
        print(f"  AUCs: {auc_str}")

        # Scheduler step
        scheduler.step(val_macro_auc)

        # Early stopping & checkpoint
        if val_macro_auc > best_macro_auc:
            best_macro_auc = val_macro_auc
            patience_counter = 0
            # Save best checkpoint
            checkpoint_dir = Path(cfg["model"]["checkpoint_dir"])
            best_checkpoint_path = checkpoint_dir / f"best_epoch{epoch}_auc{val_macro_auc:.4f}.pt"
            save_checkpoint(
                best_checkpoint_path,
                model,
                pathologies=NIH_LABELS,
                labels_es=cfg["labels_es"],
                metrics={"macro_auc": val_macro_auc, "per_class_auc": val_aucs, "val_loss": val_loss},
                extra={"epoch": epoch, "phase": "head", "config": cfg},
            )
            print(f"  >> New best macro AUC: {best_macro_auc:.4f} (saved)")
        else:
            patience_counter += 1
            if patience_counter >= cfg["train"]["early_stopping_patience"]:
                print(f"Early stopping triggered at epoch {epoch}")
                break

    # Load best head-only checkpoint for phase 2
    if best_checkpoint_path and best_checkpoint_path.exists():
        print(f"\nLoading best head-only checkpoint: {best_checkpoint_path}")
        ckpt = load_checkpoint(best_checkpoint_path)
        model.load_state_dict(ckpt["state_dict"], strict=True)

    # ==================== PHASE 2: Partial Unfreeze ====================
    print(f"\n{'='*60}")
    print(f"PHASE 2: Partial unfreeze ({cfg['train']['epochs_finetune']} epochs)")
    print(f"{'='*60}")
    unfreeze_partial(model)
    trainable, _ = count_trainable_params(model)
    print(f"Trainable params: {trainable:,}")

    optimizer = optim.AdamW(
        filter(lambda p: p.requires_grad, model.parameters()),
        lr=cfg["train"]["lr_finetune"],
        weight_decay=cfg["train"]["weight_decay"],
    )
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode="max", factor=0.5, patience=2, verbose=True
    )

    finetune_start_epoch = cfg["train"]["epochs_head"]
    for epoch in range(finetune_start_epoch, finetune_start_epoch + cfg["train"]["epochs_finetune"]):
        epoch_start = time.time()

        train_loss = train_one_epoch(
            model, train_loader, optimizer, criterion, device, use_amp, scaler,
            cfg["train"]["grad_clip"], epoch, writer
        )

        val_loss, val_aucs, val_macro_auc = validate(model, val_loader, device, use_amp)
        epoch_time = time.time() - epoch_start

        writer.add_scalar("train/epoch_loss", train_loss, epoch)
        writer.add_scalar("val/epoch_loss", val_loss, epoch)
        writer.add_scalar("val/macro_auc", val_macro_auc, epoch)
        for i, auc in enumerate(val_aucs):
            if not (isinstance(auc, float) and auc != auc):
                writer.add_scalar(f"val/auc_{NIH_LABELS[i]}", auc, epoch)

        auc_str = " | ".join(
            f"{NIH_LABELS[i]}: {auc:.4f}" if not (isinstance(auc, float) and auc != auc) else f"{NIH_LABELS[i]}: NaN"
            for i, auc in enumerate(val_aucs)
        )
        print(
            f"Epoch {epoch:3d}/{finetune_start_epoch + cfg['train']['epochs_finetune'] - 1} | "
            f"train_loss: {train_loss:.4f} | val_loss: {val_loss:.4f} | "
            f"macro_AUC: {val_macro_auc:.4f} | time: {epoch_time:.1f}s"
        )
        print(f"  AUCs: {auc_str}")

        scheduler.step(val_macro_auc)

        if val_macro_auc > best_macro_auc:
            best_macro_auc = val_macro_auc
            patience_counter = 0
            checkpoint_dir = Path(cfg["model"]["checkpoint_dir"])
            best_checkpoint_path = checkpoint_dir / f"best_epoch{epoch}_auc{val_macro_auc:.4f}.pt"
            save_checkpoint(
                best_checkpoint_path,
                model,
                pathologies=NIH_LABELS,
                labels_es=cfg["labels_es"],
                metrics={"macro_auc": val_macro_auc, "per_class_auc": val_aucs, "val_loss": val_loss},
                extra={"epoch": epoch, "phase": "finetune", "config": cfg},
            )
            print(f"  >> New best macro AUC: {best_macro_auc:.4f} (saved)")
        else:
            patience_counter += 1
            if patience_counter >= cfg["train"]["early_stopping_patience"]:
                print(f"Early stopping triggered at epoch {epoch}")
                break

    # ==================== Final: Save production checkpoint ====================
    print(f"\n{'='*60}")
    print("FINAL: Saving production checkpoint")
    print(f"{'='*60}")

    # Load best overall checkpoint
    if best_checkpoint_path and best_checkpoint_path.exists():
        ckpt = load_checkpoint(best_checkpoint_path)
        model.load_state_dict(ckpt["state_dict"], strict=True)
        best_metrics = ckpt.get("metrics", {})
    else:
        best_metrics = {"macro_auc": best_macro_auc}

    final_path = Path(cfg["model"]["checkpoint_dir"]) / cfg["model"]["checkpoint_name"]
    save_checkpoint(
        final_path,
        model,
        pathologies=NIH_LABELS,
        labels_es=cfg["labels_es"],
        metrics=best_metrics,
        extra={"config": cfg, "total_epochs": epoch + 1},
    )

    writer.close()
    print(f"\nTraining complete!")
    print(f"Best macro AUC: {best_macro_auc:.4f}")
    print(f"Final checkpoint: {final_path}")
    print(f"TensorBoard: tensorboard --logdir {log_dir}")


if __name__ == "__main__":
    main()