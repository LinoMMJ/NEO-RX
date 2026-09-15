"""
Evaluation Script for Fine-tuned Model

Computes comprehensive metrics on test set:
- AUC-ROC per class + macro average
- Sensitivity, Specificity, F1 at Youden's J threshold
- Confusion matrices
- Saves metrics.json and optional AUC curves plot
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import (
    auc,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset import get_dataloaders, NIH_LABELS
from training.model import load_finetuned_model


def parse_args():
    parser = argparse.ArgumentParser(description="Evaluate fine-tuned model on test set")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("training/config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        required=True,
        help="Path to fine-tuned checkpoint .pt",
    )
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        choices=["auto", "cuda", "cpu"],
        help="Device to use (default: auto)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output metrics.json path (default: checkpoint_dir/metrics.json)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate AUC curves plot (requires matplotlib)",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_device(device_arg: str) -> torch.device:
    if device_arg == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_arg)


def find_optimal_threshold(y_true: np.ndarray, y_scores: np.ndarray) -> float:
    """Find threshold maximizing Youden's J (sensitivity + specificity - 1)."""
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    j_scores = tpr - fpr
    idx = np.argmax(j_scores)
    return float(thresholds[idx])


def compute_metrics(
    targets: np.ndarray,
    probs: np.ndarray,
) -> Dict:
    """Compute all metrics for a single class."""
    n_samples = len(targets)
    n_positive = int(targets.sum())
    n_negative = n_samples - n_positive

    if n_positive == 0 or n_negative == 0:
        return {
            "auc": float("nan"),
            "sensitivity": float("nan"),
            "specificity": float("nan"),
            "f1": float("nan"),
            "threshold": 0.5,
            "n_positive": n_positive,
            "n_negative": n_negative,
            "confusion_matrix": [[0, 0], [0, 0]],
        }

    # AUC
    auc_score = roc_auc_score(targets, probs)

    # Optimal threshold via Youden's J
    threshold = find_optimal_threshold(targets, probs)
    preds = (probs >= threshold).astype(int)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(targets, preds).ravel()

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = f1_score(targets, preds) if (tp + fp + fn) > 0 else 0.0

    return {
        "auc": float(auc_score),
        "sensitivity": float(sensitivity),
        "specificity": float(specificity),
        "precision": float(precision),
        "f1": float(f1),
        "threshold": float(threshold),
        "n_positive": n_positive,
        "n_negative": n_negative,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def evaluate_model(
    model: nn.Module,
    test_loader,
    device: torch.device,
) -> Tuple[np.ndarray, np.ndarray]:
    """Run inference on test set, return (targets, probs) as numpy arrays."""
    model.eval()
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for images, targets, _ in test_loader:
            images = images.to(device, non_blocking=True)
            # Use model.model for raw logits, then sigmoid
            logits = model.model(images)
            probs = torch.sigmoid(logits)

            all_targets.append(targets.cpu().numpy())
            all_probs.append(probs.cpu().numpy())

    all_targets = np.vstack(all_targets)  # [N, 14]
    all_probs = np.vstack(all_probs)      # [N, 14]
    return all_targets, all_probs


def print_metrics_table(metrics: Dict, labels: List[str]) -> None:
    """Print formatted metrics table."""
    print(f"\n{'Class':<25} {'AUC':>8} {'Sens':>8} {'Spec':>8} {'F1':>8} {'Thresh':>8} {'Pos':>6} {'Neg':>6}")
    print("-" * 85)

    valid_aucs = []
    for i, label in enumerate(labels):
        m = metrics[label]
        if isinstance(m["auc"], float) and m["auc"] != m["auc"]:  # NaN
            auc_str = "   NaN"
        else:
            auc_str = f"{m['auc']:8.4f}"
            valid_aucs.append(m["auc"])

        sens_str = f"{m['sensitivity']:8.4f}" if not (isinstance(m['sensitivity'], float) and m['sensitivity'] != m['sensitivity']) else "   NaN"
        spec_str = f"{m['specificity']:8.4f}" if not (isinstance(m['specificity'], float) and m['specificity'] != m['specificity']) else "   NaN"
        f1_str = f"{m['f1']:8.4f}" if not (isinstance(m['f1'], float) and m['f1'] != m['f1']) else "   NaN"
        thresh_str = f"{m['threshold']:8.4f}"

        print(f"{label:<25} {auc_str} {sens_str} {spec_str} {f1_str} {thresh_str} {m['n_positive']:6d} {m['n_negative']:6d}")

    macro_auc = np.mean(valid_aucs) if valid_aucs else float("nan")
    print("-" * 85)
    print(f"{'MACRO AVERAGE':<25} {macro_auc:8.4f}")
    print()


def plot_auc_curves(
    targets: np.ndarray,
    probs: np.ndarray,
    labels: List[str],
    output_path: Path,
) -> None:
    """Generate and save AUC-ROC curves plot."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping plot")
        return

    n_classes = len(labels)
    n_cols = 4
    n_rows = (n_classes + n_cols - 1) // n_cols

    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4 * n_cols, 3 * n_rows))
    axes = axes.flatten() if n_rows * n_cols > 1 else [axes]

    for i, label in enumerate(labels):
        if targets[:, i].sum() == 0 or targets[:, i].sum() == len(targets):
            axes[i].text(0.5, 0.5, "No positive/negative samples", ha="center", va="center")
            axes[i].set_title(label)
            continue

        fpr, tpr, _ = roc_curve(targets[:, i], probs[:, i])
        roc_auc = auc(fpr, tpr)

        axes[i].plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
        axes[i].plot([0, 1], [0, 1], "k--", alpha=0.3)
        axes[i].set_xlabel("False Positive Rate")
        axes[i].set_ylabel("True Positive Rate")
        axes[i].set_title(label)
        axes[i].legend(loc="lower right")
        axes[i].grid(True, alpha=0.3)

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"AUC curves plot saved to {output_path}")


def main():
    args = parse_args()
    cfg = load_config(args.config)
    device = get_device(args.device)

    print(f"Device: {device}")
    print(f"Checkpoint: {args.checkpoint}")

    # DataLoader
    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    _, _, test_loader = get_dataloaders(cfg, splits_json, data_dir)

    # Load model
    model = load_finetuned_model(args.checkpoint).to(device)
    print(f"Model loaded: {len(model.pathologies)} classes")
    print(f"Pathologies: {model.pathologies}")

    # Evaluate
    print("\nRunning evaluation on test set...")
    targets, probs = evaluate_model(model, test_loader, device)
    print(f"Test samples: {len(targets)}")

    # Compute per-class metrics
    metrics = {}
    for i, label in enumerate(NIH_LABELS):
        metrics[label] = compute_metrics(targets[:, i], probs[:, i])

    # Print table
    print_metrics_table(metrics, NIH_LABELS)

    # Macro AUC
    valid_aucs = [m["auc"] for m in metrics.values() if not (isinstance(m["auc"], float) and m["auc"] != m["auc"])]
    macro_auc = np.mean(valid_aucs) if valid_aucs else float("nan")
    print(f"MACRO AUC: {macro_auc:.4f}")

    # Prepare output
    output_data = {
        "model": "resnet50_finetuned_nih",
        "checkpoint": str(args.checkpoint),
        "test_samples": int(len(targets)),
        "labels": NIH_LABELS,
        "per_class": metrics,
        "macro_auc": float(macro_auc),
    }

    # Save metrics.json
    if args.output:
        output_path = args.output
    else:
        output_path = args.checkpoint.parent / "metrics.json"

    with open(output_path, "w") as f:
        # Convert numpy types to Python types for JSON
        def convert(obj):
            if isinstance(obj, (np.integer, np.floating)):
                return float(obj) if isinstance(obj, np.floating) else int(obj)
            if isinstance(obj, np.ndarray):
                return obj.tolist()
            if isinstance(obj, dict):
                return {k: convert(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [convert(v) for v in obj]
            return obj

        json.dump(convert(output_data), f, indent=2)

    print(f"Metrics saved to {output_path}")

    # Plot
    if args.plot:
        plot_path = output_path.with_suffix(".png").with_name(output_path.stem + "_auc_curves.png")
        plot_auc_curves(targets, probs, NIH_LABELS, plot_path)


if __name__ == "__main__":
    main()