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
from training.configuration import get_target_labels
from training.model import (
    build_model,
    count_trainable_params,
    load_checkpoint,
    save_checkpoint,
    set_head_only,
    unfreeze_partial,
)
from training.threshold_optimizer import ThresholdOptimizer, save_thresholds_csv
from training.session import BudgetExpired, check_deadline, resume_signature


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
    parser.add_argument('--max-hours', type=float, default=0,
                        help='Stop safely at a batch boundary; 0 means unlimited. Resume repeats an unfinished epoch.')
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


def compute_average_precision_scores(
    targets: np.ndarray, probs: np.ndarray
) -> Tuple[List[float], float]:
    """Compute PR-AUC per class; more informative for rare findings than ROC-AUC."""
    from sklearn.metrics import average_precision_score

    scores = []
    for index in range(targets.shape[1]):
        truth = targets[:, index]
        if truth.sum() == 0 or truth.sum() == len(truth):
            scores.append(float("nan"))
        else:
            scores.append(float(average_precision_score(truth, probs[:, index])))
    valid = [score for score in scores if not np.isnan(score)]
    return scores, float(np.mean(valid)) if valid else 0.0


def validate(
    model: nn.Module,
    loader,
    device: torch.device,
    use_amp: bool,
    criterion: Optional[nn.Module] = None,
    deadline=None,
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
            check_deadline(deadline)
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
    deadline=None,
) -> float:
    """Train one epoch, return average loss."""
    model.train()
    # Frozen backbone BatchNorm statistics must not drift during head training.
    for module in model.modules():
        if isinstance(module, nn.modules.batchnorm._BatchNorm) and not any(
            parameter.requires_grad for parameter in module.parameters()
        ):
            module.eval()
    total_loss = 0.0
    n_batches = 0

    for batch_idx, (images, targets, _) in enumerate(loader):
        check_deadline(deadline)
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

        if batch_idx % 100 == 0:
            print(f'Epoch {epoch}: batch {batch_idx + 1}/{len(loader)} loss={loss.item():.4f}', flush=True)

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
    """Calculate TRAIN-only class weights without decoding images when metadata is available."""
    print("Calculating pos_weight from TRAIN split...")
    pos_counts = torch.zeros(num_classes, dtype=torch.long)
    dataset = train_loader.dataset

    if hasattr(dataset, "df") and hasattr(dataset, "label_to_idx") and "labels" in dataset.df:
        total_counts = len(dataset)
        for sample_labels in dataset.df["labels"]:
            for label in sample_labels:
                index = dataset.label_to_idx.get(label)
                if index is not None:
                    pos_counts[index] += 1
        print("  source: validated manifest metadata")
    else:
        total_counts = 0
        for _, targets, _ in train_loader:
            pos_counts += targets.sum(dim=0).long()
            total_counts += targets.shape[0]
        print("  source: DataLoader fallback")

    neg_counts = total_counts - pos_counts
    pos_weight = torch.ones(num_classes, dtype=torch.float32)
    for index in range(num_classes):
        if pos_counts[index] > 0:
            pos_weight[index] = neg_counts[index].float() / pos_counts[index].float()
        else:
            print(f"  WARNING: Class {index} has 0 positive samples in TRAIN, pos_weight=1.0")

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
    if args.max_hours < 0:
        raise ValueError('--max-hours must be non-negative')
    deadline = time.monotonic() + args.max_hours * 3600 if args.max_hours else None
    device = get_device(args.device)
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is not available")
    set_seed(cfg["train"]["seed"])
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Config: {args.config}")

    if args.max_samples and cfg.get("safety", {}).get("require_full_dataset", False):
        raise ValueError(
            "This configuration is reserved for the final full-data run; "
            "remove --max-samples or use a separate pilot configuration."
        )

    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    train_loader, val_loader, _ = get_dataloaders(
        cfg, splits_json, data_dir, max_samples=args.max_samples
    )
    if args.max_samples:
        actual = len(train_loader.dataset) + len(val_loader.dataset)
        print(f"PIPELINE TEST: {actual:,} train+validation samples loaded")

    labels = get_target_labels(cfg)
    num_classes = len(labels)
    model = build_model(cfg).to(device)
    print(f"Training with {num_classes} classes: {labels}")

    resume = load_checkpoint(args.resume) if args.resume else None
    signature = resume_signature(cfg)
    if resume:
        if resume.get('pathologies') != labels:
            raise ValueError('Resume labels differ from the configured labels')
        previous_signature = resume.get('training_state', {}).get('resume_signature')
        if previous_signature != signature:
            raise ValueError('Resume dataset/configuration changed or checkpoint is from an older pipeline. Use the matching overnight package.')
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
    if resume and not (args.resume.parent / 'best.pt').exists() and resume.get('training_state', {}).get('best_selection_score', -1) >= 0:
        raise ValueError('Resume requires best.pt alongside last.pt; attach the complete previous output')
    if not resume and (best_path.exists() or last_path.exists()):
        raise ValueError('Checkpoint directory is not empty; explicitly resume or use a new output directory')
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
    selection_metric = cfg["train"].get("selection_metric", "macro_auc")
    if selection_metric not in {
        "macro_auc", "macro_average_precision", "primary_average_precision",
        "minimum_class_auc",
    }:
        raise ValueError("Unsupported train.selection_metric")
    primary_labels = cfg.get('decision_strategy', {}).get('primary_labels', [])
    if selection_metric == 'primary_average_precision' and (not primary_labels or not set(primary_labels).issubset(labels)):
        raise ValueError('primary_average_precision requires primary_labels included in target_labels')
    resume_metrics = resume.get("metrics", {}) if resume else {}
    default_selection = (
        resume_metrics.get("macro_average_precision", 0.0)
        if selection_metric == "macro_average_precision"
        else resume_metrics.get("macro_auc", 0.0)
    )
    if selection_metric == 'primary_average_precision':
        default_selection = resume_metrics.get('selection_score', 0.0) if resume_metrics.get('selection_metric') == selection_metric else 0.0
    best_selection_score = float(saved_state.get("best_selection_score", default_selection if resume else -1.0))
    patience_counter = int(saved_state.get("patience_counter", 0))
    best_thresholds = resume.get("thresholds") if resume else None
    best_decision_policy = resume.get("decision_policy") if resume else None
    _restore_rng_state(saved_state.get("rng_state"))

    head_epochs = int(cfg["train"]["epochs_head"])
    total_epochs = head_epochs + int(cfg["train"]["epochs_finetune"])
    if resume_phase == "finetune" and next_epoch < head_epochs:
        raise ValueError("Invalid resume checkpoint: finetune phase before head epochs")
    if next_epoch >= total_epochs:
        print("All configured epochs were already completed; rebuilding final checkpoint only.")

    stop_reason = 'completed'
    if resume_phase == 'finetune' and patience_counter >= cfg['train']['early_stopping_patience']:
        stop_reason = 'early_stopped'
    epoch_durations = []

    def run_phase(phase: str, start: int, stop: int, learning_rate: float, patience: int):
        nonlocal best_macro_auc, best_selection_score, best_thresholds, best_decision_policy, patience_counter, next_epoch, stop_reason
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

        if not last_path.exists():
            save_checkpoint(last_path, model, labels, cfg['labels_es'], extra={'config': cfg},
                            training_state={'phase': phase, 'next_epoch': start,
                                            'best_selection_score': best_selection_score,
                                            'rng_state': _capture_rng_state(), 'resume_signature': signature})

        for epoch in range(start, stop):
            if deadline and epoch_durations and time.monotonic() + max(epoch_durations) * 1.2 >= deadline:
                stop_reason = 'paused_time_budget'
                return
            started = time.time()
            try:
                train_loss = train_one_epoch(
                    model, train_loader, optimizer, criterion, device, use_amp, scaler,
                    cfg["train"]["grad_clip"], epoch, writer, deadline=deadline,
                )
                val_loss, val_aucs, val_macro_auc, val_targets, val_probs = validate(
                    model, val_loader, device, use_amp, criterion, deadline=deadline,
                )
            except BudgetExpired:
                stop_reason = 'paused_time_budget'
                print('Time budget reached. The unfinished epoch will repeat from last.pt.', flush=True)
                return
            val_aps, val_macro_ap = compute_average_precision_scores(val_targets, val_probs)
            selection_score = (
                val_macro_ap if selection_metric == "macro_average_precision" else val_macro_auc
            )
            if selection_metric == 'primary_average_precision':
                primary_aps = [val_aps[labels.index(label)] for label in primary_labels]
                selection_score = float(np.mean(primary_aps)) if np.isfinite(primary_aps).all() else 0.0
            elif selection_metric == 'minimum_class_auc':
                # A macro average can hide one weak category.  Selecting by the
                # worst class makes a checkpoint improve the floor shared by
                # every configured output instead of optimizing Effusion only.
                selection_score = float(np.min(val_aucs)) if np.isfinite(val_aucs).all() else 0.0
            current_lr = optimizer.param_groups[0]["lr"]
            writer.add_scalar("train/epoch_loss", train_loss, epoch)
            writer.add_scalar("val/epoch_loss", val_loss, epoch)
            writer.add_scalar("val/macro_auc", val_macro_auc, epoch)
            writer.add_scalar("val/macro_average_precision", val_macro_ap, epoch)
            for index, auc in enumerate(val_aucs):
                if not np.isnan(auc):
                    writer.add_scalar(f"val/auc_{labels[index]}", auc, epoch)
            log_epoch_csv(
                history_csv, epoch, phase, train_loss, val_loss,
                val_aucs, val_macro_auc, labels, current_lr,
            )
            scheduler.step(selection_score)
            improved = selection_score > best_selection_score
            if improved:
                best_selection_score = selection_score
                best_macro_auc = val_macro_auc
                patience_counter = 0
                threshold_cfg = cfg.get("threshold", {})
                optimizer_threshold = ThresholdOptimizer(
                    method=threshold_cfg.get("method", "youden_j"),
                    min_threshold=threshold_cfg.get("min_threshold", 0.05),
                    max_threshold=threshold_cfg.get("max_threshold", 0.95),
                    target_precision=threshold_cfg.get("target_precision", 0.85),
                    min_sensitivity=threshold_cfg.get("min_sensitivity", 0.0),
                    target_sensitivity=threshold_cfg.get("target_sensitivity", 0.80),
                    min_specificity=threshold_cfg.get("min_specificity", 0.0),
                    min_predictions=threshold_cfg.get("min_predictions", 1),
                    min_positive_support=threshold_cfg.get("min_positive_support", 1),
                )
                threshold_results = optimizer_threshold.get_detailed_results(
                    val_targets, val_probs, labels
                )
                best_thresholds = [threshold_results[label].threshold for label in labels]
                best_decision_policy = {
                    label: {
                        "enabled": threshold_results[label].enabled,
                        "status": threshold_results[label].status,
                        "threshold": threshold_results[label].threshold,
                        "validation_precision": threshold_results[label].validation_precision,
                        "validation_sensitivity": threshold_results[label].validation_sensitivity,
                        "validation_positive_support": threshold_results[label].n_positive,
                        "validation_predicted_positive": threshold_results[label].predicted_positive,
                        "selection_method": threshold_results[label].selection_method,
                    }
                    for label in labels
                }
                save_thresholds_csv(threshold_results, run_dir / "thresholds_validation.csv")
                save_checkpoint(
                    best_path, model, labels, cfg["labels_es"],
                    metrics={
                        "macro_auc": val_macro_auc,
                        "per_class_auc": val_aucs,
                        "macro_average_precision": val_macro_ap,
                        "per_class_average_precision": val_aps,
                        "selection_metric": selection_metric,
                        "selection_score": selection_score,
                        "val_loss": val_loss,
                    },
                    extra={"epoch": epoch, "phase": phase, "config": cfg},
                    thresholds=best_thresholds,
                    decision_policy=best_decision_policy,
                    pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
                )
            else:
                patience_counter += 1
            next_epoch = epoch + 1
            training_state = {
                "phase": phase,
                "next_epoch": next_epoch,
                "best_macro_auc": best_macro_auc,
                "best_selection_score": best_selection_score,
                "selection_metric": selection_metric,
                "patience_counter": patience_counter,
                "optimizer_state": optimizer.state_dict(),
                "scheduler_state": scheduler.state_dict(),
                "scaler_state": scaler.state_dict(),
                "rng_state": _capture_rng_state(),
                "resume_signature": signature,
            }
            save_checkpoint(
                last_path, model, labels, cfg["labels_es"],
                metrics={
                    "macro_auc": val_macro_auc,
                    "per_class_auc": val_aucs,
                    "macro_average_precision": val_macro_ap,
                    "per_class_average_precision": val_aps,
                    "selection_metric": selection_metric,
                    "selection_score": selection_score,
                    "val_loss": val_loss,
                },
                extra={"epoch": epoch, "phase": phase, "config": cfg},
                thresholds=best_thresholds,
                decision_policy=best_decision_policy,
                pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
                training_state=training_state,
            )
            state_json = {
                "phase": phase,
                "last_completed_epoch": epoch,
                "next_epoch": next_epoch,
                "best_macro_auc": best_macro_auc,
                "best_selection_score": best_selection_score,
                "selection_metric": selection_metric,
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
                f"macro_AP={val_macro_ap:.4f} time={time.time() - started:.1f}s "
                f"best_{selection_metric}={best_selection_score:.4f}"
            )
            epoch_durations.append(time.time() - started)
            print(f'Estimated remaining training: {(total_epochs - next_epoch) * np.mean(epoch_durations) / 3600:.2f} hours (approximate)', flush=True)
            if patience_counter >= patience:
                print(f"Early stopping in {phase} after epoch {epoch}")
                if phase == 'finetune':
                    stop_reason = 'early_stopped'
                break

    if resume_phase == "head":
        run_phase(
            "head", min(next_epoch, head_epochs), head_epochs,
            cfg["train"]["lr_head"], cfg["train"]["early_stopping_patience"],
        )
        if stop_reason != 'paused_time_budget' and best_path.exists():
            model.load_state_dict(load_checkpoint(best_path)["state_dict"], strict=True)
        if stop_reason != 'paused_time_budget':
            patience_counter = 0
            next_epoch = max(next_epoch, head_epochs)

    if stop_reason == 'completed':
        run_phase(
            "finetune", max(next_epoch, head_epochs), total_epochs,
            cfg["train"]["lr_finetune"], cfg["train"]["early_stopping_patience"],
        )

    status = {'status': stop_reason, 'next_epoch': next_epoch, 'total_epochs': total_epochs,
              'training_finished': stop_reason in ('completed', 'early_stopped'),
              'best_checkpoint_available': best_path.exists(), 'test_evaluated': False}
    (checkpoint_dir / 'session_status.json').write_text(json.dumps(status, indent=2), encoding='utf-8')
    if stop_reason == 'paused_time_budget':
        writer.close()
        print(json.dumps(status), flush=True)
        return

    if best_path.exists():
        best_checkpoint = load_checkpoint(best_path)
        model.load_state_dict(best_checkpoint["state_dict"], strict=True)
        best_metrics = best_checkpoint.get("metrics", {})
        best_thresholds = best_checkpoint.get("thresholds", best_thresholds)
        best_decision_policy = best_checkpoint.get("decision_policy", best_decision_policy)
    else:
        best_metrics = {
            "macro_auc": best_macro_auc,
            "selection_metric": selection_metric,
            "selection_score": best_selection_score,
        }

    final_path = checkpoint_dir / cfg["model"]["checkpoint_name"]
    save_checkpoint(
        final_path, model, labels, cfg["labels_es"], metrics=best_metrics,
        extra={"config": cfg, "total_epochs": min(next_epoch, total_epochs), "experiment": cfg.get("experiment", {})},
        thresholds=_threshold_list(best_thresholds, labels),
        decision_policy=best_decision_policy,
        pos_weight=pos_weight.detach().cpu().tolist() if pos_weight is not None else None,
    )
    writer.close()
    print(
        f"Training complete. Best {selection_metric}: {best_selection_score:.4f}; "
        f"macro AUC at selected checkpoint: {best_macro_auc:.4f}"
    )
    print(f"Final checkpoint: {final_path}")


if __name__ == "__main__":
    main()
