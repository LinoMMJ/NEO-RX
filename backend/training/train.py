"""
Training Loop for Fine-tuning on NIH ChestX-ray14

Two-stage training:
  1. Head-only (epochs 1-N): only fc layer trainable
  2. Partial unfreeze (epochs N+1-M): layer3, layer4, fc trainable

Uses BCEWithLogitsLoss on raw logits (model.model(x)), NOT xrv forward (which applies sigmoid).
Mixed precision, gradient clipping, early stopping, TensorBoard logging.
CSV logging for training history.
Threshold optimization on VALIDATION only (never on TEST).
pos_weight calculated from TRAIN split only.

IMPORTANT: All metrics are PENDIENTE DE EJECUCIÓN EXPERIMENTAL.
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import yaml
from torch.cuda.amp import GradScaler, autocast
from torch.utils.tensorboard import SummaryWriter

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset import get_dataloaders
from training.model import (
    build_model,
    count_trainable_params,
    load_checkpoint,
    save_checkpoint,
    set_head_only,
    unfreeze_partial,
)
from training.threshold_optimizer import ThresholdOptimizer


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
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit samples for quick pipeline test (e.g., 2000). NOT for final results.",
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


def validate(
    model: nn.Module,
    loader,
    device: torch.device,
    use_amp: bool,
    criterion: Optional[nn.Module] = None,
) -> Tuple[float, List[float], float, np.ndarray, np.ndarray]:
    """
    Run validation, return (loss, per_class_aucs, macro_auc, all_targets, all_probs).

    Returns targets and probs for threshold optimization.
    """
    model.eval()
    if criterion is None:
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

    return avg_loss, aucs, macro_auc, all_targets.numpy(), all_probs.numpy()


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


def log_epoch_csv(csv_path: Path, epoch: int, phase: str, train_loss: float,
                  val_loss: float, val_aucs: List[float], val_macro_auc: float,
                  labels: List[str], lr: float):
    """Append epoch results to CSV training history."""
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            # Header
            header = ["epoch", "phase", "train_loss", "val_loss", "val_macro_auc", "learning_rate"]
            header.extend([f"val_auc_{label}" for label in labels])
            writer.writerow(header)
        row = [epoch, phase, train_loss, val_loss, val_macro_auc, lr]
        row.extend([auc if not (isinstance(auc, float) and auc != auc) else "" for auc in val_aucs])
        writer.writerow(row)


def calculate_pos_weight(train_loader, num_classes: int, device: torch.device) -> torch.Tensor:
    """
    Calculate pos_weight for BCEWithLogitsLoss from TRAIN split only.

    pos_weight = num_negative / num_positive for each class.
    This balances the loss for imbalanced multi-label classification.

    Returns:
        Tensor of shape [num_classes] with pos_weight for each class.
    """
    print("Calculating pos_weight from TRAIN split...")
    pos_counts = torch.zeros(num_classes, dtype=torch.long)
    total_counts = 0

    for _, targets, _ in train_loader:
        pos_counts += targets.sum(dim=0).long()
        total_counts += targets.shape[0]

    neg_counts = total_counts - pos_counts

    # Avoid division by zero: if a class has no positive samples, set weight to 1.0
    pos_weight = torch.ones(num_classes, dtype=torch.float32)
    for i in range(num_classes):
        if pos_counts[i] > 0:
            pos_weight[i] = neg_counts[i].float() / pos_counts[i].float()
        else:
            pos_weight[i] = 1.0
            print(f"  WARNING: Class {i} has 0 positive samples in TRAIN, pos_weight=1.0")

    print(f"  pos_weight: {pos_weight.tolist()}")
    print(f"  pos_counts: {pos_counts.tolist()}")
    print(f"  neg_counts: {neg_counts.tolist()}")

    return pos_weight.to(device)


def _capture_rng_state() -> Dict:
    import random
    state = {
        "python": random.getstate(),
        "numpy": np.random.get_state(),
        "torch": torch.get_rng_state(),
    }
    if torch.cuda.is_available():
        state["cuda"] = torch.cuda.get_rng_state_all()
    return state


def _restore_rng_state(state: Optional[Dict]) -> None:
    if not state:
        return
    import random
    random.setstate(state["python"])
    np.random.set_state(state["numpy"])
    torch.set_rng_state(state["torch"])
    if torch.cuda.is_available() and state.get("cuda"):
        torch.cuda.set_rng_state_all(state["cuda"])


def _threshold_list(value, labels):
    if isinstance(value, dict):
        return [float(value[label]) for label in labels]
    return value


def main():
    args = parse_args()
    cfg = load_config(args.config)
    device = get_device(args.device)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    set_seed(cfg["train"]["seed"])
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Config: {args.config}")

    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    train_loader, val_loader, _ = get_dataloaders(
        cfg, splits_json, data_dir, max_samples=args.max_samples
    )
    if args.max_samples:
        actual = len(train_loader.dataset) + len(val_loader.dataset)
        print(f"PIPELINE TEST: {actual:,} train+validation samples loaded")

    labels = cfg.get("pulmonary_labels", cfg.get("nih_labels", []))
    num_classes = len(labels)
    model = build_model(cfg).to(device)
    print(f"Training with {num_classes} classes: {labels}")

    resume = load_checkpoint(args.resume) if args.resume else None
    if resume:
        model.load_state_dict(resume["state_dict"], strict=True)
        print(f"Loaded resume checkpoint: {args.resume}")

    if cfg["train"].get("use_pos_weight", True):
        pos_weight = calculate_pos_weight(train_loader, num_classes, device)
        criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)
    else:
        pos_weight = None
        criterion = nn.BCEWithLogitsLoss()

    use_amp = bool(cfg["train"].get("mixed_precision", True) and device.type == "cuda")
    scaler = GradScaler(enabled=use_amp)
    checkpoint_dir = Path(cfg["model"]["checkpoint_dir"])
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    best_path = checkpoint_dir / "best.pt"
    last_path = checkpoint_dir / "last.pt"
    if resume and args.resume.parent.joinpath("best.pt").exists() and not best_path.exists():
        import shutil
        shutil.copy2(args.resume.parent / "best.pt", best_path)

    experiment_name = cfg.get("experiment", {}).get("name", "training")
    run_dir = Path(cfg["train"]["log_dir"]) / experiment_name
    run_dir.mkdir(parents=True, exist_ok=True)
    writer = SummaryWriter(log_dir=run_dir)
    history_csv = run_dir / "training_history.csv"

    saved_state = resume.get("training_state", {}) if resume else {}
    resume_phase = saved_state.get("phase", resume.get("extra", {}).get("phase", "head") if resume else "head")
    next_epoch = int(saved_state.get("next_epoch", resume.get("extra", {}).get("epoch", -1) + 1 if resume else 0))
    best_macro_auc = float(saved_state.get("best_macro_auc", resume.get("metrics", {}).get("macro_auc", 0.0) if resume else 0.0))
    patience_counter = int(saved_state.get("patience_counter", 0))
    best_thresholds = resume.get("thresholds") if resume else None
    _restore_rng_state(saved_state.get("rng_state"))

    head_epochs = int(cfg["train"]["epochs_head"])
    total_epochs = head_epochs + int(cfg["train"]["epochs_finetune"])
    if resume_phase == "finetune" and next_epoch < head_epochs:
        raise ValueError("Invalid resume checkpoint: finetune phase before head epochs")
    if next_epoch >= total_epochs:
        print("All configured epochs were already completed; rebuilding final checkpoint only.")

    def run_phase(phase: str, start: int, stop: int, learning_rate: float, patience: int):
        nonlocal best_macro_auc, best_thresholds, patience_counter, next_epoch
        if start >= stop:
            return
        if phase == "head":
            set_head_only(model, freeze=True)
        else:
            unfreeze_partial(model)
        trainable, total = count_trainable_params(model)
        print(f"\n{phase.upper()}: epochs {start}..{stop - 1}; {trainable:,}/{total:,} trainable params")
        optimizer = optim.AdamW(
            filter(lambda parameter: parameter.requires_grad, model.parameters()),
            lr=learning_rate,
            weight_decay=cfg["train"]["weight_decay"],
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="max", factor=0.5, patience=2
        )
        if resume and saved_state.get("phase") == phase and start == next_epoch:
            if saved_state.get("optimizer_state"):
                optimizer.load_state_dict(saved_state["optimizer_state"])
            if saved_state.get("scheduler_state"):
                scheduler.load_state_dict(saved_state["scheduler_state"])
            if saved_state.get("scaler_state"):
                scaler.load_state_dict(saved_state["scaler_state"])
            print(f"Restored optimizer, scheduler and AMP state for {phase} at epoch {start}")

        for epoch in range(start, stop):
            started = time.time()
            train_loss = train_one_epoch(
                model, train_loader, optimizer, criterion, device, use_amp, scaler,
                cfg["train"]["grad_clip"], epoch, writer,
            )
            val_loss, val_aucs, val_macro_auc, val_targets, val_probs = validate(
                model, val_loader, device, use_amp, criterion
            )
            current_lr = optimizer.param_groups[0]["lr"]
            writer.add_scalar("train/epoch_loss", train_loss, epoch)
            writer.add_scalar("val/epoch_loss", val_loss, epoch)
            writer.add_scalar("val/macro_auc", val_macro_auc, epoch)
            for index, auc in enumerate(val_aucs):
                if not np.isnan(auc):
                    writer.add_scalar(f"val/auc_{labels[index]}", auc, epoch)
            log_epoch_csv(
                history_csv, epoch, phase, train_loss, val_loss,
                val_aucs, val_macro_auc, labels, current_lr,
            )
            scheduler.step(val_macro_auc)
            improved = val_macro_auc > best_macro_auc
            if improved:
                best_macro_auc = val_macro_auc
                patience_counter = 0
                threshold_cfg = cfg.get("threshold", {})
                optimizer_threshold = ThresholdOptimizer(
                    method=threshold_cfg.get("method", "youden_j"),
                    min_threshold=threshold_cfg.get("min_threshold", 0.05),
                    max_threshold=threshold_cfg.get("max_threshold", 0.95),
                )
                best_thresholds = optimizer_threshold.optimize(val_targets, val_probs, labels)
                save_checkpoint(
                    best_path, model, labels, cfg["labels_es"],
                    metrics={"macro_auc": val_macro_auc, "per_class_auc": val_aucs, "val_loss": val_loss},
                    extra={"epoch": epoch, "phase": phase, "config": cfg},
                    thresholds=best_thresholds,
                    pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
                )
            else:
                patience_counter += 1
            next_epoch = epoch + 1
            training_state = {
                "phase": phase,
                "next_epoch": next_epoch,
                "best_macro_auc": best_macro_auc,
                "patience_counter": patience_counter,
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "scaler_state": scaler.state_dict(),
                "rng_state": _capture_rng_state(),
            }
            save_checkpoint(
                last_path, model, labels, cfg["labels_es"],
                metrics={"macro_auc": val_macro_auc, "per_class_auc": val_aucs, "val_loss": val_loss},
                extra={"epoch": epoch, "phase": phase, "config": cfg},
                thresholds=best_thresholds,
                pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
                training_state=training_state,
            )
            state_json = {
                "phase": phase,
                "last_completed_epoch": epoch,
                "next_epoch": next_epoch,
                "best_macro_auc": best_macro_auc,
                "patience_counter": patience_counter,
                "safe_to_resume": True,
                "last_checkpoint": str(last_path),
                "best_checkpoint": str(best_path),
            }
            with open(checkpoint_dir / "run_state.json", "w", encoding="utf-8") as handle:
                json.dump(state_json, handle, indent=2)
            print(
                f"Epoch {epoch}/{stop - 1} {phase} | train={train_loss:.4f} "
                f"val={val_loss:.4f} macro_AUC={val_macro_auc:.4f} "
                f"time={time.time() - started:.1f}s best={best_macro_auc:.4f}"
            )
            if patience_counter >= patience:
                print(f"Early stopping in {phase} after epoch {epoch}")
                break

    if resume_phase == "head":
        run_phase(
            "head", min(next_epoch, head_epochs), head_epochs,
            cfg["train"]["lr_head"], cfg["train"]["early_stopping_patience"],
        )
        if best_path.exists():
            model.load_state_dict(load_checkpoint(best_path)["state_dict"], strict=True)
        patience_counter = 0
        next_epoch = max(next_epoch, head_epochs)

    run_phase(
        "finetune", max(next_epoch, head_epochs), total_epochs,
        cfg["train"]["lr_finetune"], cfg["train"]["early_stopping_patience"],
    )

    if best_path.exists():
        best_checkpoint = load_checkpoint(best_path)
        model.load_state_dict(best_checkpoint["state_dict"], strict=True)
        best_metrics = best_checkpoint.get("metrics", {})
        best_thresholds = best_checkpoint.get("thresholds", best_thresholds)
    else:
        best_metrics = {"macro_auc": best_macro_auc}

    final_path = checkpoint_dir / cfg["model"]["checkpoint_name"]
    save_checkpoint(
        final_path, model, labels, cfg["labels_es"], metrics=best_metrics,
        extra={"config": cfg, "total_epochs": min(next_epoch, total_epochs), "experiment": cfg.get("experiment", {})},
        thresholds=_threshold_list(best_thresholds, labels),
        pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
    )
    writer.close()
    print(f"Training complete. Best macro AUC: {best_macro_auc:.4f}")
    print(f"Final checkpoint: {final_path}")


if __name__ == "__main__":
    main()
