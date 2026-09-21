"""Create deterministic patient-level train/validation/test splits from a clean manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

PULMONARY_LABELS = [
    "Atelectasis", "Consolidation", "Edema", "Emphysema", "Effusion", "Fibrosis",
    "Infiltration", "Mass", "Nodule", "Pleural_Thickening", "Pneumonia", "Pneumothorax",
]
NIH_LABELS = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema", "Effusion", "Emphysema",
    "Fibrosis", "Hernia", "Infiltration", "Mass", "Nodule", "Pleural_Thickening",
    "Pneumonia", "Pneumothorax",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Create leakage-safe NIH patient splits")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--labels", choices=("pulmonary", "nih"), default="pulmonary")
    parser.add_argument("--train-ratio", type=float, default=0.70)
    parser.add_argument("--val-ratio", type=float, default=0.15)
    parser.add_argument("--test-ratio", type=float, default=0.15)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--attempts", type=int, default=64)
    return parser.parse_args()


def label_matrix(frame: pd.DataFrame, labels: list[str]) -> np.ndarray:
    sets = frame["Finding Labels"].fillna("").map(lambda value: set(str(value).split("|")))
    return np.asarray([[label in found for label in labels] for found in sets], dtype=np.int8)


def split_for_seed(frame, seed, train_ratio, val_ratio):
    patients = frame["Patient ID"].drop_duplicates().to_numpy()
    train_patients, temporary = train_test_split(
        patients, train_size=train_ratio, random_state=seed, shuffle=True
    )
    relative_val = val_ratio / (1.0 - train_ratio)
    val_patients, test_patients = train_test_split(
        temporary, train_size=relative_val, random_state=seed, shuffle=True
    )
    assignment = {}
    assignment.update({patient: "train" for patient in train_patients})
    assignment.update({patient: "val" for patient in val_patients})
    assignment.update({patient: "test" for patient in test_patients})
    return frame["Patient ID"].map(assignment)


def candidate_score(frame, assignment, labels):
    overall = label_matrix(frame, labels).mean(axis=0)
    score, counts = 0.0, {}
    for name in ("train", "val", "test"):
        part = frame[assignment == name]
        matrix = label_matrix(part, labels)
        positive = matrix.sum(axis=0)
        counts[name] = positive
        if len(part) == 0 or np.any(positive == 0):
            return float("inf"), counts
        score += float(np.abs(matrix.mean(axis=0) - overall).sum())
    return score, counts


def main():
    args = parse_args()
    if not np.isclose(args.train_ratio + args.val_ratio + args.test_ratio, 1.0):
        raise ValueError("train/val/test ratios must sum to 1")
    frame = pd.read_csv(args.manifest)
    required = {"Image Index", "Finding Labels", "Patient ID"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Manifest is missing columns: {missing}")
    labels = PULMONARY_LABELS if args.labels == "pulmonary" else NIH_LABELS
    best = None
    for offset in range(max(1, args.attempts)):
        seed = args.seed + offset
        assignment = split_for_seed(frame, seed, args.train_ratio, args.val_ratio)
        score, counts = candidate_score(frame, assignment, labels)
        if best is None or score < best[0]:
            best = (score, seed, assignment, counts)
    if best is None or not np.isfinite(best[0]):
        raise RuntimeError("Could not create splits containing positives for every selected label")
    score, selected_seed, assignment, counts = best
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    splits = {
        name: frame.loc[assignment == name, "Image Index"].astype(str).tolist()
        for name in ("train", "val", "test")
    }
    patient_sets = {
        name: set(frame.loc[assignment == name, "Patient ID"].tolist())
        for name in ("train", "val", "test")
    }
    if patient_sets["train"] & patient_sets["val"] or patient_sets["train"] & patient_sets["test"] or patient_sets["val"] & patient_sets["test"]:
        raise RuntimeError("Patient leakage detected")
    with open(output / "splits.json", "w", encoding="utf-8") as handle:
        json.dump(splits, handle, indent=2)
    statistics = {
        "seed": selected_seed,
        "distribution_score": score,
        "labels": labels,
        "splits": {
            name: {
                "images": len(splits[name]),
                "patients": len(patient_sets[name]),
                "positive_by_label": {label: int(counts[name][i]) for i, label in enumerate(labels)},
            }
            for name in ("train", "val", "test")
        },
        "patient_overlap": 0,
    }
    with open(output / "split_summary.json", "w", encoding="utf-8") as handle:
        json.dump(statistics, handle, indent=2, ensure_ascii=False)
    print(json.dumps(statistics, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
