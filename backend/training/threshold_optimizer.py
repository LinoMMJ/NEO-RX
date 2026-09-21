"""
Threshold Optimization for Multi-label Classification

Optimizes decision thresholds on VALIDATION set only.
Never uses TEST set for threshold selection.

Method: Youden's J statistic (sensitivity + specificity - 1)
Alternative methods can be added (F1-max, fixed sensitivity, etc.)

All results are PENDIENTE DE EJECUCIÓN EXPERIMENTAL.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.metrics import roc_curve, precision_recall_curve, f1_score


@dataclass
class ThresholdResult:
    """Result of threshold optimization for a single class."""
    threshold: float
    validation_auc: float
    validation_f1: float
    validation_sensitivity: float
    validation_specificity: float
    validation_precision: float
    selection_method: str
    n_positive: int
    n_negative: int


class ThresholdOptimizer:
    """
    Optimize classification thresholds for multi-label classification.

    Works exclusively on VALIDATION data. Never on TEST.
    """

    def __init__(
        self,
        method: str = "youden_j",
        min_threshold: float = 0.05,
        max_threshold: float = 0.95
    ):
        """
        Args:
            method: "youden_j" (default), "f1_max", "fixed_sensitivity"
            min_threshold: Minimum threshold to consider
            max_threshold: Maximum threshold to consider
        """
        self.method = method
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold

    def optimize(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        labels: List[str]
    ) -> List[float]:
        """
        Optimize thresholds for all classes.

        Args:
            y_true: [N, C] binary ground truth
            y_scores: [N, C] predicted probabilities
            labels: List of class names

        Returns:
            List of optimal thresholds (one per class)
        """
        n_classes = y_true.shape[1]
        thresholds = []

        for i in range(n_classes):
            thresholds.append(self._optimize_single_class(
                y_true[:, i], y_scores[:, i], labels[i]
            ))

        return thresholds

    def _optimize_single_class(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        label: str
    ) -> float:
        """Optimize threshold for a single class."""
        n_pos = int(y_true.sum())
        n_neg = len(y_true) - n_pos

        # Handle edge cases
        if n_pos == 0 or n_neg == 0:
            # No positive or negative samples - use default
            return 0.5

        if self.method == "youden_j":
            return self._youden_j_threshold(y_true, y_scores)
        elif self.method == "f1_max":
            return self._f1_max_threshold(y_true, y_scores)
        elif self.method == "fixed_sensitivity":
            return self._fixed_sensitivity_threshold(y_true, y_scores, target_sensitivity=0.90)
        else:
            raise ValueError(f"Unknown threshold method: {self.method}")

    def _youden_j_threshold(self, y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """
        Youden's J = sensitivity + specificity - 1 = TPR - FPR
        Maximizes the vertical distance between ROC curve and diagonal.
        """
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        j_scores = tpr - fpr

        # Filter thresholds within bounds
        valid_mask = (thresholds >= self.min_threshold) & (thresholds <= self.max_threshold)
        if not valid_mask.any():
            return 0.5

        valid_j = j_scores[valid_mask]
        valid_thresholds = thresholds[valid_mask]
        best_idx = np.argmax(valid_j)

        return float(valid_thresholds[best_idx])

    def _f1_max_threshold(self, y_true: np.ndarray, y_scores: np.ndarray) -> float:
        """Threshold that maximizes F1 score."""
        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)

        # precision_recall_curve returns thresholds of length len(precision)-1
        # Append 1.0 for the last point
        thresholds = np.append(thresholds, 1.0)

        # Filter thresholds within bounds
        valid_mask = (thresholds >= self.min_threshold) & (thresholds <= self.max_threshold)
        if not valid_mask.any():
            return 0.5

        f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
        valid_f1 = f1_scores[valid_mask]
        valid_thresholds = thresholds[valid_mask]
        best_idx = np.argmax(valid_f1)

        return float(valid_thresholds[best_idx])

    def _fixed_sensitivity_threshold(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        target_sensitivity: float = 0.90
    ) -> float:
        """
        Find threshold achieving at least target_sensitivity with max specificity.
        """
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)

        # Filter thresholds within bounds
        valid_mask = (thresholds >= self.min_threshold) & (thresholds <= self.max_threshold)
        if not valid_mask.any():
            return 0.5

        valid_tpr = tpr[valid_mask]
        valid_fpr = fpr[valid_mask]
        valid_thresholds = thresholds[valid_mask]

        # Find thresholds with sensitivity >= target
        sensitivity_mask = valid_tpr >= target_sensitivity
        if not sensitivity_mask.any():
            # No threshold achieves target sensitivity - use max sensitivity
            best_idx = np.argmax(valid_tpr)
        else:
            # Among those, pick one with minimum FPR (max specificity)
            candidate_fpr = valid_fpr[sensitivity_mask]
            candidate_thresholds = valid_thresholds[sensitivity_mask]
            best_idx = np.argmin(candidate_fpr)
            best_idx = np.where(sensitivity_mask)[0][best_idx]

        return float(valid_thresholds[best_idx])

    def get_detailed_results(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        labels: List[str]
    ) -> Dict[str, ThresholdResult]:
        """
        Get detailed threshold optimization results for all classes.

        Returns:
            Dict mapping label -> ThresholdResult
        """
        results = {}

        for i, label in enumerate(labels):
            n_pos = int(y_true[:, i].sum())
            n_neg = len(y_true) - n_pos

            if n_pos == 0 or n_neg == 0:
                results[label] = ThresholdResult(
                    threshold=0.5,
                    validation_auc=float("nan"),
                    validation_f1=float("nan"),
                    validation_sensitivity=float("nan"),
                    validation_specificity=float("nan"),
                    validation_precision=float("nan"),
                    selection_method=self.method,
                    n_positive=n_pos,
                    n_negative=n_neg,
                )
                continue

            # Compute AUC
            try:
                from sklearn.metrics import roc_auc_score
                auc = roc_auc_score(y_true[:, i], y_scores[:, i])
            except (ImportError, ValueError):
                auc = float("nan")

            # Find optimal threshold
            threshold = self._optimize_single_class(y_true[:, i], y_scores[:, i], label)
            preds = (y_scores[:, i] >= threshold).astype(int)

            # Compute metrics at this threshold
            tp = int(((preds == 1) & (y_true[:, i] == 1)).sum())
            fp = int(((preds == 1) & (y_true[:, i] == 0)).sum())
            tn = int(((preds == 0) & (y_true[:, i] == 0)).sum())
            fn = int(((preds == 0) & (y_true[:, i] == 1)).sum())

            sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
            specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
            f1 = f1_score(y_true[:, i], preds) if (tp + fp + fn) > 0 else 0.0

            results[label] = ThresholdResult(
                threshold=threshold,
                validation_auc=auc,
                validation_f1=f1,
                validation_sensitivity=sensitivity,
                validation_specificity=specificity,
                validation_precision=precision,
                selection_method=self.method,
                n_positive=n_pos,
                n_negative=n_neg,
            )

        return results


def save_thresholds_csv(results: Dict[str, ThresholdResult], output_path: Path) -> None:
    """Save threshold optimization results to CSV."""
    import csv

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "class", "threshold", "validation_auc", "validation_f1",
            "validation_sensitivity", "validation_specificity",
            "validation_precision", "selection_method",
            "n_positive", "n_negative"
        ])
        for label, result in results.items():
            writer.writerow([
                label,
                f"{result.threshold:.6f}",
                f"{result.validation_auc:.6f}" if not np.isnan(result.validation_auc) else "NaN",
                f"{result.validation_f1:.6f}" if not np.isnan(result.validation_f1) else "NaN",
                f"{result.validation_sensitivity:.6f}" if not np.isnan(result.validation_sensitivity) else "NaN",
                f"{result.validation_specificity:.6f}" if not np.isnan(result.validation_specificity) else "NaN",
                f"{result.validation_precision:.6f}" if not np.isnan(result.validation_precision) else "NaN",
                result.selection_method,
                result.n_positive,
                result.n_negative,
            ])


def load_thresholds_csv(csv_path: Path) -> Dict[str, float]:
    """Load thresholds from CSV file."""
    import csv

    thresholds = {}
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            thresholds[row["class"]] = float(row["threshold"])
    return thresholds
