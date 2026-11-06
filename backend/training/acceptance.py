"""Frozen TEST acceptance gate for a completed NeoRX experiment.

The gate reports evidence; it never changes thresholds or model weights.
"""
from __future__ import annotations

from typing import Dict, Iterable


def build_acceptance_report(
    metrics: Dict,
    labels: Iterable[str],
    acceptance: Dict,
) -> Dict:
    floors = {
        "auc": float(acceptance.get("minimum_auc_per_class", 0.80)),
        "sensitivity": float(acceptance.get("minimum_sensitivity_per_class", 0.80)),
        "specificity": float(acceptance.get("minimum_specificity_per_class", 0.70)),
    }
    if any(not 0 <= value <= 1 for value in floors.values()):
        raise ValueError("Acceptance metric floors must be between 0 and 1")

    classes = {}
    for label in labels:
        values = metrics[label]
        checks = {
            metric: values.get(metric) is not None and float(values[metric]) >= floor
            for metric, floor in floors.items()
        }
        classes[label] = {
            "passed": all(checks.values()),
            "checks": checks,
            "observed": {metric: values.get(metric) for metric in floors},
        }
    passed = bool(classes) and all(item["passed"] for item in classes.values())
    return {
        "passed": passed,
        "deployment_recommendation": "eligible_for_review" if passed else "do_not_deploy",
        "criteria": floors,
        "classes": classes,
        "note": (
            "Internal held-out TEST gate only; passing does not replace external clinical "
            "validation or professional interpretation."
        ),
    }
