"""Validated access to the pathology set used by a training experiment."""

from __future__ import annotations

from typing import Dict, List


def get_target_labels(cfg: Dict) -> List[str]:
    """Return the configured labels while keeping older configs compatible."""
    labels = cfg.get("target_labels")
    if labels is None:
        labels = cfg.get("pulmonary_labels", cfg.get("nih_labels", []))
    if not isinstance(labels, list) or not labels:
        raise ValueError("The config must define a non-empty target_labels list")
    if not all(isinstance(label, str) and label.strip() for label in labels):
        raise ValueError("Every target label must be a non-empty string")
    labels = [label.strip() for label in labels]
    if len(set(labels)) != len(labels):
        raise ValueError("target_labels contains duplicates")

    configured_classes = cfg.get("model", {}).get("num_classes")
    if configured_classes is not None and int(configured_classes) != len(labels):
        raise ValueError(
            f"model.num_classes={configured_classes} does not match "
            f"the {len(labels)} configured target_labels"
        )
    return labels
