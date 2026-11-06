"""
Threshold Optimization for Multi-label Classification

Optimizes decision thresholds on VALIDATION set only.
Never uses TEST set for threshold selection.

Method: Youden's J statistic (sensitivity + specificity - 1)
Supports Youden J, F1-max, fixed sensitivity, fixed precision and a guarded
precision/recall operating point that can disable unsupported classes.

All results are PENDIENTE DE EJECUCIÓN EXPERIMENTAL.
"""

from dataclasses import dataclass
from pathlib import Path
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
    enabled: bool = True
    status: str = "enabled"
    predicted_positive: int = 0


class ThresholdOptimizer:
    """
    Optimize classification thresholds for multi-label classification.

    Works exclusively on VALIDATION data. Never on TEST.
    """

    def __init__(
        self,
        method: str = "youden_j",
        min_threshold: float = 0.05,
        max_threshold: float = 0.95,
        target_precision: float = 0.85,
        min_sensitivity: float = 0.0,
        target_sensitivity: float = 0.80,
        min_specificity: float = 0.0,
        min_predictions: int = 1,
        min_positive_support: int = 1,
    ):
        """
        Args:
            method: "youden_j", "f1_max", "fixed_sensitivity",
                "fixed_precision" or "precision_recall_guarded"
            min_threshold: Minimum threshold to consider
            max_threshold: Maximum threshold to consider
        """
        self.method = method
        self.min_threshold = min_threshold
        self.max_threshold = max_threshold
        if not 0 < target_precision <= 1:
            raise ValueError("target_precision must be in (0, 1]")
        self.target_precision = target_precision
        if not 0 <= min_sensitivity <= 1:
            raise ValueError("min_sensitivity must be in [0, 1]")
        if min_predictions < 1 or min_positive_support < 1:
            raise ValueError("minimum support values must be positive")
        self.min_sensitivity = min_sensitivity
        if not 0 < target_sensitivity <= 1:
            raise ValueError("target_sensitivity must be in (0, 1]")
        if not 0 <= min_specificity <= 1:
            raise ValueError("min_specificity must be in [0, 1]")
        self.target_sensitivity = target_sensitivity
        self.min_specificity = min_specificity
        self.min_predictions = int(min_predictions)
        self.min_positive_support = int(min_positive_support)

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
        elif self.method == "fixed_precision":
            return self._fixed_precision_threshold(y_true, y_scores, self.target_precision)
        elif self.method == "precision_recall_guarded":
            threshold = self._guarded_threshold(y_true, y_scores)
            return self.max_threshold if threshold is None else threshold
        elif self.method == "sensitivity_specificity_guarded":
            threshold = self._sensitivity_specificity_guarded_threshold(y_true, y_scores)
            return self.max_threshold if threshold is None else threshold
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

    def _fixed_precision_threshold(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
        target_precision: float,
    ) -> float:
        """Maximize recall among thresholds that meet a precision floor.

        When validation cannot support the requested precision, use the maximum
        allowed threshold. This conservative fallback avoids silently replacing
        a precision objective with a high-false-positive operating point.
        """
        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
        if not len(thresholds):
            return self.max_threshold
        precision = precision[:-1]
        recall = recall[:-1]
        valid = (
            (thresholds >= self.min_threshold)
            & (thresholds <= self.max_threshold)
            & (precision >= target_precision)
        )
        if not valid.any():
            return self.max_threshold

        indices = np.where(valid)[0]
        # Highest recall first; ties prefer greater precision and then a higher
        # threshold, producing the more conservative decision rule.
        best = max(indices, key=lambda i: (recall[i], precision[i], thresholds[i]))
        return float(thresholds[best])

    def _guarded_threshold(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
    ) -> Optional[float]:
        """Select a threshold only when validation supports a useful decision.

        Unlike the legacy fixed-precision method, failure to meet the requested
        precision, sensitivity and sample-support floors returns ``None``.  The
        caller then records the class as disabled instead of manufacturing a
        very high threshold with near-zero recall.
        """
        if int(y_true.sum()) < self.min_positive_support:
            return None
        precision, recall, thresholds = precision_recall_curve(y_true, y_scores)
        if not len(thresholds):
            return None
        precision = precision[:-1]
        recall = recall[:-1]
        sorted_scores = np.sort(y_scores)
        predicted_positive = len(sorted_scores) - np.searchsorted(
            sorted_scores, thresholds, side="left"
        )
        valid = (
            (thresholds >= self.min_threshold)
            & (thresholds <= self.max_threshold)
            & (precision >= self.target_precision)
            & (recall >= self.min_sensitivity)
            & (predicted_positive >= self.min_predictions)
        )
        if not valid.any():
            return None
        indices = np.where(valid)[0]
        best = max(indices, key=lambda i: (recall[i], precision[i], thresholds[i]))
        return float(thresholds[best])

    def _sensitivity_specificity_guarded_threshold(
        self,
        y_true: np.ndarray,
        y_scores: np.ndarray,
    ) -> Optional[float]:
        """Meet a sensitivity target without accepting unusable specificity.

        This is intended for screening-style support.  If validation cannot
        satisfy both floors, the class is disabled rather than silently
        lowering the decision threshold and flooding the UI with positives.
        """
        if int(y_true.sum()) < self.min_positive_support:
            return None
        fpr, tpr, thresholds = roc_curve(y_true, y_scores)
        specificity = 1.0 - fpr
        predicted_positive = np.asarray([(y_scores >= value).sum() for value in thresholds])
        valid = (
            (thresholds >= self.min_threshold)
            & (thresholds <= self.max_threshold)
            & (tpr >= self.target_sensitivity)
            & (specificity >= self.min_specificity)
            & (predicted_positive >= self.min_predictions)
        )
        if not valid.any():
            return None
        indices = np.where(valid)[0]
        # Prefer specificity once the requested sensitivity is reached; ties
        # prefer greater sensitivity and then the more conservative threshold.
        best = max(indices, key=lambda i: (specificity[i], tpr[i], thresholds[i]))
        return float(thresholds[best])

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
                guarded = self.method in {
                    "precision_recall_guarded", "sensitivity_specificity_guarded"
                }
                results[label] = ThresholdResult(
                    threshold=self.max_threshold if guarded else 0.5,
                    validation_auc=float("nan"),
                    validation_f1=float("nan"),
                    validation_sensitivity=float("nan"),
                    validation_specificity=float("nan"),
                    validation_precision=float("nan"),
                    selection_method=self.method,
                    n_positive=n_pos,
                    n_negative=n_neg,
                    enabled=not guarded,
                    status="insufficient_classes" if guarded else "enabled",
                )
                continue

            # Compute AUC
            try:
                from sklearn.metrics import roc_auc_score
                auc = roc_auc_score(y_true[:, i], y_scores[:, i])
            except (ImportError, ValueError):
                auc = float("nan")

            enabled = True
            status = "enabled"
            if self.method in {"precision_recall_guarded", "sensitivity_specificity_guarded"}:
                if n_pos < self.min_positive_support:
                    threshold = self.max_threshold
                    enabled = False
                    status = "insufficient_positive_support"
                else:
                    candidate = (
                        self._guarded_threshold(y_true[:, i], y_scores[:, i])
                        if self.method == "precision_recall_guarded"
                        else self._sensitivity_specificity_guarded_threshold(
                            y_true[:, i], y_scores[:, i]
                        )
                    )
                    threshold = self.max_threshold if candidate is None else candidate
                    enabled = candidate is not None
                    status = "enabled" if enabled else "operating_point_not_met"
            else:
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
                enabled=enabled,
                status=status,
                predicted_positive=int(preds.sum()),
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
            "n_positive", "n_negative", "predicted_positive", "enabled", "status"
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
                result.predicted_positive,
                str(result.enabled).lower(),
                result.status,
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
