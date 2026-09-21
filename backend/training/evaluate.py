"""
Evaluation Script for Fine-tuned Model

Computes comprehensive metrics on TEST set using thresholds from VALIDATION (stored in checkpoint).
Never recalculates thresholds on TEST set.

Outputs:
- metrics.csv: Per-class AUC, sensitivity, specificity, precision, F1, threshold
- thresholds.csv: Thresholds used (from checkpoint)
- classification_report.json: Detailed per-class metrics
- confusion_matrix.csv: Confusion matrices per class (binary one-vs-rest)
- ROC curves plot (optional)
- PR curves plot (optional)

IMPORTANT: All metrics are PENDIENTE DE EJECUCIÓN EXPERIMENTAL.
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import torch
import torch.nn as nn
import yaml
from sklearn.metrics import (
    auc,
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset import get_dataloaders
from training.model import load_finetuned_model, get_thresholds_from_checkpoint


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
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: checkpoint parent directory)",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate ROC/PR curves plots (requires matplotlib)",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_device(device_arg: str) -> torch.device:
    if device_arg == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_arg)


def compute_metrics(
    targets: np.ndarray,
    probs: np.ndarray,
    threshold: float,
) -> Dict:
    """Compute all metrics for a single class using the provided threshold."""
    n_samples = len(targets)
    n_positive = int(targets.sum())
    n_negative = n_samples - n_positive

    if n_positive == 0 or n_negative == 0:
        return {
            "auc": float("nan"),
            "average_precision": float("nan"),
            "sensitivity": float("nan"),
            "specificity": float("nan"),
            "precision": float("nan"),
            "f1": float("nan"),
            "threshold": threshold,
            "n_positive": n_positive,
            "n_negative": n_negative,
            "confusion_matrix": [[0, 0], [0, 0]],
        }

    # AUC-ROC
    try:
        auc_score = roc_auc_score(targets, probs)
    except ValueError:
        auc_score = float("nan")

    # Average Precision (PR-AUC)
    try:
        ap_score = average_precision_score(targets, probs)
    except ValueError:
        ap_score = float("nan")

    # Predictions using threshold from checkpoint (VALIDATION)
    preds = (probs >= threshold).astype(int)

    # Confusion matrix
    tn, fp, fn, tp = confusion_matrix(targets, preds).ravel()

    sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = f1_score(targets, preds) if (tp + fp + fn) > 0 else 0.0

    return {
        "auc": float(auc_score),
        "average_precision": float(ap_score),
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
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Run inference on test set and preserve stable image identifiers."""
    model.eval()
    all_targets = []
    all_probs = []
    all_image_ids = []

    with torch.no_grad():
        for images, targets, image_ids in test_loader:
            images = images.to(device, non_blocking=True)
            # Use model.model for raw logits, then sigmoid
            logits = model.model(images)
            probs = torch.sigmoid(logits)

            all_targets.append(targets.cpu().numpy())
            all_probs.append(probs.cpu().numpy())
            all_image_ids.extend(list(image_ids))

    all_targets = np.vstack(all_targets)  # [N, C]
    all_probs = np.vstack(all_probs)      # [N, C]
    return all_targets, all_probs, all_image_ids


def print_metrics_table(metrics: Dict, labels: List[str]) -> None:
    """Print formatted metrics table."""
    print(f"\n{'Class':<25} {'AUC':>8} {'AP':>8} {'Sens':>8} {'Spec':>8} {'Prec':>8} {'F1':>8} {'Thresh':>8} {'Pos':>6} {'Neg':>6}")
    print("-" * 105)

    valid_aucs = []
    valid_aps = []
    for i, label in enumerate(labels):
        m = metrics[label]
        if isinstance(m["auc"], float) and m["auc"] != m["auc"]:  # NaN
            auc_str = "   NaN"
        else:
            auc_str = f"{m['auc']:8.4f}"
            valid_aucs.append(m["auc"])

        if isinstance(m["average_precision"], float) and m["average_precision"] != m["average_precision"]:
            ap_str = "   NaN"
        else:
            ap_str = f"{m['average_precision']:8.4f}"
            valid_aps.append(m["average_precision"])

        sens_str = f"{m['sensitivity']:8.4f}" if not (isinstance(m['sensitivity'], float) and m['sensitivity'] != m['sensitivity']) else "   NaN"
        spec_str = f"{m['specificity']:8.4f}" if not (isinstance(m['specificity'], float) and m['specificity'] != m['specificity']) else "   NaN"
        prec_str = f"{m['precision']:8.4f}" if not (isinstance(m['precision'], float) and m['precision'] != m['precision']) else "   NaN"
        f1_str = f"{m['f1']:8.4f}" if not (isinstance(m['f1'], float) and m['f1'] != m['f1']) else "   NaN"
        thresh_str = f"{m['threshold']:8.4f}"

        print(f"{label:<25} {auc_str} {ap_str} {sens_str} {spec_str} {prec_str} {f1_str} {thresh_str} {m['n_positive']:6d} {m['n_negative']:6d}")

    macro_auc = np.mean(valid_aucs) if valid_aucs else float("nan")
    macro_ap = np.mean(valid_aps) if valid_aps else float("nan")
    print("-" * 105)
    print(f"{'MACRO AVERAGE':<25} {macro_auc:8.4f} {macro_ap:8.4f}")
    print()


def save_metrics_csv(metrics: Dict, labels: List[str], output_path: Path) -> None:
    """Save per-class metrics to CSV."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "class", "auc", "average_precision", "sensitivity", "specificity",
            "precision", "f1", "threshold", "n_positive", "n_negative"
        ])
        for label in labels:
            m = metrics[label]
            writer.writerow([
                label,
                f"{m['auc']:.6f}" if not np.isnan(m['auc']) else "NaN",
                f"{m['average_precision']:.6f}" if not np.isnan(m['average_precision']) else "NaN",
                f"{m['sensitivity']:.6f}" if not np.isnan(m['sensitivity']) else "NaN",
                f"{m['specificity']:.6f}" if not np.isnan(m['specificity']) else "NaN",
                f"{m['precision']:.6f}" if not np.isnan(m['precision']) else "NaN",
                f"{m['f1']:.6f}" if not np.isnan(m['f1']) else "NaN",
                f"{m['threshold']:.6f}",
                m['n_positive'],
                m['n_negative'],
            ])


def save_thresholds_csv(thresholds: Dict[str, float], labels: List[str], output_path: Path) -> None:
    """Save thresholds to CSV."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["class", "threshold"])
        for label in labels:
            writer.writerow([label, f"{thresholds.get(label, 0.5):.6f}"])


def save_confusion_matrix_csv(metrics: Dict, labels: List[str], output_path: Path) -> None:
    """Save confusion matrices to CSV (one row per class)."""
    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["class", "tn", "fp", "fn", "tp"])
        for label in labels:
            m = metrics[label]
            tn, fp = m["confusion_matrix"][0]
            fn, tp = m["confusion_matrix"][1]
            writer.writerow([label, tn, fp, fn, tp])


def save_classification_report_json(
    metrics: Dict,
    labels: List[str],
    macro_auc: float,
    macro_ap: float,
    test_samples: int,
    checkpoint_path: str,
    output_path: Path
) -> None:
    """Save detailed classification report as JSON."""
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

    output_data = {
        "model": "resnet50_finetuned_nih",
        "checkpoint": checkpoint_path,
        "test_samples": int(test_samples),
        "labels": labels,
        "macro_auc": float(macro_auc) if not np.isnan(macro_auc) else None,
        "macro_average_precision": float(macro_ap) if not np.isnan(macro_ap) else None,
        "per_class": {label: convert(metrics[label]) for label in labels},
        "note": "All metrics computed on TEST set using thresholds from VALIDATION (stored in checkpoint). PENDIENTE DE EJECUCIÓN EXPERIMENTAL."
    }

    with open(output_path, "w") as f:
        json.dump(convert(output_data), f, indent=2)


def plot_roc_curves(
    targets: np.ndarray,
    probs: np.ndarray,
    labels: List[str],
    thresholds: Dict[str, float],
    output_path: Path,
) -> None:
    """Generate and save ROC curves plot with threshold markers."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping ROC plot")
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

        fpr, tpr, thresh = roc_curve(targets[:, i], probs[:, i])
        roc_auc = auc(fpr, tpr)

        axes[i].plot(fpr, tpr, label=f"AUC = {roc_auc:.3f}")
        axes[i].plot([0, 1], [0, 1], "k--", alpha=0.3)

        # Mark the threshold point from validation
        threshold = thresholds.get(label, 0.5)
        # Find closest threshold point on curve
        idx = np.argmin(np.abs(thresh - threshold))
        if idx < len(fpr):
            axes[i].plot(fpr[idx], tpr[idx], 'ro', markersize=6,
                        label=f"Threshold = {threshold:.3f}")

        axes[i].set_xlabel("False Positive Rate")
        axes[i].set_ylabel("True Positive Rate")
        axes[i].set_title(label)
        axes[i].legend(loc="lower right", fontsize=8)
        axes[i].grid(True, alpha=0.3)

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"ROC curves plot saved to {output_path}")


def plot_pr_curves(
    targets: np.ndarray,
    probs: np.ndarray,
    labels: List[str],
    thresholds: Dict[str, float],
    output_path: Path,
) -> None:
    """Generate and save Precision-Recall curves plot with threshold markers."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed, skipping PR plot")
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

        precision, recall, thresh = precision_recall_curve(targets[:, i], probs[:, i])
        ap = average_precision_score(targets[:, i], probs[:, i])

        axes[i].plot(recall, precision, label=f"AP = {ap:.3f}")
        axes[i].plot([0, 1], [targets[:, i].mean(), targets[:, i].mean()], "k--", alpha=0.3, label="Baseline")

        # Mark the threshold point from validation
        threshold = thresholds.get(label, 0.5)
        # Find closest threshold point on curve
        idx = np.argmin(np.abs(thresh - threshold))
        if idx < len(precision) - 1:  # precision/recall are one longer than thresholds
            axes[i].plot(recall[idx], precision[idx], 'ro', markersize=6,
                        label=f"Threshold = {threshold:.3f}")

        axes[i].set_xlabel("Recall")
        axes[i].set_ylabel("Precision")
        axes[i].set_title(label)
        axes[i].legend(loc="lower left", fontsize=8)
        axes[i].grid(True, alpha=0.3)
        axes[i].set_xlim([0, 1])
        axes[i].set_ylim([0, 1])

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"PR curves plot saved to {output_path}")


def plot_confusion_matrices(
    targets: np.ndarray,
    probs: np.ndarray,
    labels: List[str],
    thresholds: Dict[str, float],
    output_path: Path,
) -> None:
    """Generate and save confusion matrix heatmaps."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import seaborn as sns
    except ImportError:
        print("matplotlib/seaborn not installed, skipping confusion matrix plot")
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

        threshold = thresholds.get(label, 0.5)
        preds = (probs[:, i] >= threshold).astype(int)

        cm = confusion_matrix(targets[:, i], preds)
        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[i],
                   xticklabels=['Neg', 'Pos'], yticklabels=['Neg', 'Pos'])
        axes[i].set_xlabel("Predicted")
        axes[i].set_ylabel("Actual")
        axes[i].set_title(f"{label}\n(thresh={threshold:.3f})")

    # Hide unused subplots
    for j in range(i + 1, len(axes)):
        axes[j].axis("off")

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"Confusion matrices plot saved to {output_path}")


def main():
    args = parse_args()
    cfg = load_config(args.config)
    device = get_device(args.device)

    print(f"Device: {device}")
    print(f"Checkpoint: {args.checkpoint}")

    # Load thresholds from checkpoint (VALIDATION thresholds)
    thresholds = get_thresholds_from_checkpoint(args.checkpoint)
    if not thresholds:
        print("WARNING: No thresholds found in checkpoint. Using default 0.5 for all classes.")
        # Will use model.pathologies after loading

    # DataLoader
    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    _, _, test_loader = get_dataloaders(cfg, splits_json, data_dir)

    # Load model
    model = load_finetuned_model(args.checkpoint).to(device)
    labels = model.pathologies
    print(f"Model loaded: {len(labels)} classes")
    print(f"Pathologies: {labels}")

    # Use thresholds from checkpoint, fallback to 0.5
    if not thresholds:
        thresholds = {label: 0.5 for label in labels}
    else:
        # Ensure all labels have thresholds
        for label in labels:
            if label not in thresholds:
                thresholds[label] = 0.5
    print(f"Using thresholds from checkpoint: {thresholds}")

    # Evaluate
    print("\nRunning evaluation on TEST set (using VALIDATION thresholds)...")
    targets, probs, image_ids = evaluate_model(model, test_loader, device)
    print(f"Test samples: {len(targets)}")

    # Compute per-class metrics using checkpoint thresholds
    metrics = {}
    for i, label in enumerate(labels):
        threshold = thresholds.get(label, 0.5)
        metrics[label] = compute_metrics(targets[:, i], probs[:, i], threshold)

    # Print table
    print_metrics_table(metrics, labels)

    # Macro averages
    valid_aucs = [m["auc"] for m in metrics.values() if not np.isnan(m["auc"])]
    valid_aps = [m["average_precision"] for m in metrics.values() if not np.isnan(m["average_precision"])]
    macro_auc = np.mean(valid_aucs) if valid_aucs else float("nan")
    macro_ap = np.mean(valid_aps) if valid_aps else float("nan")
    print(f"MACRO AUC: {macro_auc:.4f}")
    print(f"MACRO AP:  {macro_ap:.4f}")

    # Output directory
    if args.output_dir:
        output_dir = args.output_dir
    else:
        output_dir = args.checkpoint.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save metrics.csv
    metrics_csv = output_dir / "metrics.csv"
    save_metrics_csv(metrics, labels, metrics_csv)
    print(f"Metrics saved to {metrics_csv}")

    # Report performance by acquisition view without changing validation thresholds.
    manifest_value = cfg.get("data", {}).get("manifest")
    if manifest_value and Path(manifest_value).exists():
        import pandas as pd
        manifest = pd.read_csv(manifest_value, usecols=["Image Index", "View Position"])
        view_by_image = dict(zip(manifest["Image Index"].astype(str), manifest["View Position"].astype(str)))
        views = np.asarray([view_by_image.get(str(image_id), "UNKNOWN") for image_id in image_ids])
        with open(output_dir / "metrics_by_view.csv", "w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["view", "class", "auc", "average_precision", "sensitivity", "specificity", "precision", "f1", "n_positive", "n_negative"])
            for view in sorted(set(views)):
                mask = views == view
                for index, label in enumerate(labels):
                    item = compute_metrics(targets[mask, index], probs[mask, index], thresholds[label])
                    writer.writerow([view, label, item["auc"], item["average_precision"], item["sensitivity"], item["specificity"], item["precision"], item["f1"], item["n_positive"], item["n_negative"]])
        print(f"Metrics by AP/PA view saved to {output_dir / 'metrics_by_view.csv'}")

    # Save thresholds.csv
    thresholds_csv = output_dir / "thresholds.csv"
    save_thresholds_csv(thresholds, labels, thresholds_csv)
    print(f"Thresholds saved to {thresholds_csv}")

    # Save confusion_matrix.csv
    cm_csv = output_dir / "confusion_matrix.csv"
    save_confusion_matrix_csv(metrics, labels, cm_csv)
    print(f"Confusion matrices saved to {cm_csv}")

    # Save classification_report.json
    report_json = output_dir / "classification_report.json"
    save_classification_report_json(
        metrics, labels, macro_auc, macro_ap,
        len(targets), str(args.checkpoint), report_json
    )
    print(f"Classification report saved to {report_json}")

    # Plots
    if args.plot:
        print("\nGenerating plots...")
        plot_roc_curves(targets, probs, labels, thresholds, output_dir / "roc_curves.png")
        plot_pr_curves(targets, probs, labels, thresholds, output_dir / "pr_curves.png")
        plot_confusion_matrices(targets, probs, labels, thresholds, output_dir / "confusion_matrices.png")


if __name__ == "__main__":
    main()
