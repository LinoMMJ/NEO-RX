"""
Comparison Script: Baseline (pretrained) vs Fine-tuned Model

Evaluates both models on the SAME test set and produces comparison metrics.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import torch
import torch.nn as nn
import torchxrayvision as xrv
import yaml
from sklearn.metrics import roc_auc_score

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from training.dataset import get_dataloaders
from training.model import load_finetuned_model


def parse_args():
    parser = argparse.ArgumentParser(description="Compare baseline vs fine-tuned model")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("training/config.yaml"),
        help="Path to config.yaml",
    )
    parser.add_argument(
        "--finetuned-checkpoint",
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
        help="Output comparison.json path",
    )
    return parser.parse_args()


def load_config(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_device(device_arg: str) -> torch.device:
    if device_arg == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(device_arg)


def evaluate_model(model: nn.Module, test_loader, device: torch.device) -> Tuple[np.ndarray, np.ndarray]:
    """Run inference, return (targets, probs) as numpy arrays."""
    model.eval()
    all_targets = []
    all_probs = []

    with torch.no_grad():
        for images, targets, _ in test_loader:
            images = images.to(device, non_blocking=True)
            logits = model.model(images)
            probs = torch.sigmoid(logits)

            all_targets.append(targets.cpu().numpy())
            all_probs.append(probs.cpu().numpy())

    return np.vstack(all_targets), np.vstack(all_probs)


def compute_aucs(targets: np.ndarray, probs: np.ndarray, labels: List[str]) -> Dict[str, float]:
    """Compute per-class AUC, return dict label->auc."""
    aucs = {}
    for i, label in enumerate(labels):
        if targets[:, i].sum() == 0 or targets[:, i].sum() == len(targets):
            aucs[label] = float("nan")
        else:
            aucs[label] = float(roc_auc_score(targets[:, i], probs[:, i]))
    return aucs


def print_comparison_table(
    baseline_aucs: Dict[str, float],
    finetuned_aucs: Dict[str, float],
    labels: List[str],
) -> None:
    """Print side-by-side comparison table."""
    print(f"\n{'Class':<25} {'Baseline':>10} {'Finetuned':>10} {'Delta':>10} {'Pct Change':>12}")
    print("-" * 72)

    baseline_valid = []
    finetuned_valid = []

    for label in labels:
        b = baseline_aucs[label]
        f = finetuned_aucs[label]

        b_nan = isinstance(b, float) and b != b
        f_nan = isinstance(f, float) and f != f

        if not b_nan:
            baseline_valid.append(b)
        if not f_nan:
            finetuned_valid.append(f)

        if b_nan or f_nan:
            delta_str = "   NaN"
            pct_str = "     NaN"
        else:
            delta = f - b
            pct = (delta / b * 100) if b > 0 else float("inf")
            delta_str = f"{delta:10.4f}"
            pct_str = f"{pct:11.1f}%"

        b_str = f"{b:10.4f}" if not b_nan else "     NaN"
        f_str = f"{f:10.4f}" if not f_nan else "     NaN"

        print(f"{label:<25} {b_str} {f_str} {delta_str} {pct_str}")

    # Macro averages
    macro_baseline = np.mean(baseline_valid) if baseline_valid else float("nan")
    macro_finetuned = np.mean(finetuned_valid) if finetuned_valid else float("nan")

    if not (isinstance(macro_baseline, float) and macro_baseline != macro_baseline) and \
       not (isinstance(macro_finetuned, float) and macro_finetuned != macro_finetuned):
        macro_delta = macro_finetuned - macro_baseline
        macro_pct = (macro_delta / macro_baseline * 100) if macro_baseline > 0 else float("inf")
        delta_str = f"{macro_delta:10.4f}"
        pct_str = f"{macro_pct:11.1f}%"
    else:
        delta_str = "   NaN"
        pct_str = "     NaN"

    b_str = f"{macro_baseline:10.4f}" if not (isinstance(macro_baseline, float) and macro_baseline != macro_baseline) else "     NaN"
    f_str = f"{macro_finetuned:10.4f}" if not (isinstance(macro_finetuned, float) and macro_finetuned != macro_finetuned) else "     NaN"

    print("-" * 72)
    print(f"{'MACRO AVERAGE':<25} {b_str} {f_str} {delta_str} {pct_str}")
    print()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    device = get_device(args.device)
    labels = list(cfg["pulmonary_labels"])

    print(f"Device: {device}")
    print(f"Finetuned checkpoint: {args.finetuned_checkpoint}")

    # DataLoader (test only)
    data_dir = Path(cfg["data"]["data_dir"])
    splits_json = Path(cfg["data"]["splits_json"])
    _, _, test_loader = get_dataloaders(cfg, splits_json, data_dir)

    # ---- Baseline model (pretrained xrv) ----
    print("\nLoading baseline model (resnet50-res512-all)...")
    baseline_model = xrv.models.ResNet(weights="resnet50-res512-all").to(device)
    # Baseline has 18 pathologies; we need to map NIH 14 to baseline's indices
    baseline_pathologies = list(baseline_model.pathologies)
    print(f"Baseline pathologies ({len(baseline_pathologies)}): {baseline_pathologies}")

    # Find indices of NIH labels in baseline
    nih_to_baseline_idx = {}
    for i, label in enumerate(labels):
        if label in baseline_pathologies:
            nih_to_baseline_idx[i] = baseline_pathologies.index(label)
        else:
            print(f"WARNING: {label} not found in baseline pathologies!")

    # Evaluate baseline
    print("Evaluating baseline on test set...")
    targets, baseline_logits = evaluate_model(baseline_model, test_loader, device)
    # Map baseline probs to NIH 14 order
    baseline_probs = np.zeros((targets.shape[0], len(labels)))
    for nih_idx, base_idx in nih_to_baseline_idx.items():
        baseline_probs[:, nih_idx] = baseline_logits[:, base_idx]

    baseline_aucs = compute_aucs(targets, baseline_probs, labels)

    # ---- Fine-tuned model ----
    print(f"\nLoading fine-tuned model from {args.finetuned_checkpoint}...")
    finetuned_model = load_finetuned_model(args.finetuned_checkpoint).to(device)
    print(f"Finetuned pathologies ({len(finetuned_model.pathologies)}): {finetuned_model.pathologies}")

    # Evaluate fine-tuned
    print("Evaluating fine-tuned on test set...")
    _, finetuned_probs = evaluate_model(finetuned_model, test_loader, device)
    finetuned_aucs = compute_aucs(targets, finetuned_probs, labels)

    # Print comparison
    print_comparison_table(baseline_aucs, finetuned_aucs, labels)

    # Per-class delta
    deltas = {}
    for label in labels:
        b = baseline_aucs[label]
        f = finetuned_aucs[label]
        if isinstance(b, float) and b != b:
            deltas[label] = None
        elif isinstance(f, float) and f != f:
            deltas[label] = None
        else:
            deltas[label] = f - b

    # Win/loss count
    wins = sum(1 for d in deltas.values() if d is not None and d > 0)
    losses = sum(1 for d in deltas.values() if d is not None and d < 0)
    ties = sum(1 for d in deltas.values() if d is not None and d == 0)
    print(f"Classes improved: {wins}, degraded: {losses}, unchanged: {ties}")

    # Output JSON
    output_data = {
        "baseline": {
            "model": "resnet50-res512-all (torchxrayvision)",
            "pathologies": baseline_pathologies,
            "per_class_auc": baseline_aucs,
            "macro_auc": float(np.mean([v for v in baseline_aucs.values() if not (isinstance(v, float) and v != v)])),
        },
        "finetuned": {
            "checkpoint": str(args.finetuned_checkpoint),
            "pathologies": finetuned_model.pathologies,
            "per_class_auc": finetuned_aucs,
            "macro_auc": float(np.mean([v for v in finetuned_aucs.values() if not (isinstance(v, float) and v != v)])),
        },
        "delta": deltas,
        "summary": {
            "improved": wins,
            "degraded": losses,
            "unchanged": ties,
        },
    }

    if args.output:
        output_path = args.output
    else:
        output_path = args.finetuned_checkpoint.parent / "comparison.json"

    with open(output_path, "w") as f:
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

    print(f"\nComparison saved to {output_path}")


if __name__ == "__main__":
    main()