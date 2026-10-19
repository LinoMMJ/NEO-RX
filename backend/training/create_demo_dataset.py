"""Create a small, reproducible NIH ChestX-ray14 demonstration set.

The set is selected *only* from the test split generated for this project.
It is therefore never mixed with the images used to fit or tune the CNN.
Run this module in Kaggle, where the original NIH images are mounted, and
download the generated directory (or its ZIP) for a classroom demonstration.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import zipfile
from collections import Counter
from pathlib import Path
from typing import Iterable


IMAGE_COLUMN = "Image Index"
LABEL_COLUMN = "Finding Labels"
PATIENT_COLUMN = "Patient ID"
VIEW_COLUMN = "View Position"
DEFAULT_LABELS = [
    "Atelectasis", "Consolidation", "Edema", "Emphysema", "Effusion",
    "Fibrosis", "Infiltration", "Mass", "Nodule", "Pleural_Thickening",
    "Pneumonia", "Pneumothorax",
]


def parse_labels(value: str) -> set[str]:
    return {label.strip() for label in value.split("|") if label.strip()}


def load_test_rows(manifest_path: Path, splits_path: Path) -> list[dict[str, str]]:
    with splits_path.open(encoding="utf-8") as handle:
        test_ids = set(json.load(handle)["test"])
    with manifest_path.open(encoding="utf-8", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if row[IMAGE_COLUMN] in test_ids]
    if len(rows) != len(test_ids):
        found = {row[IMAGE_COLUMN] for row in rows}
        raise ValueError(f"The manifest is missing {len(test_ids - found)} test images.")
    return rows


def select_rows(rows: list[dict[str, str]], count: int, seed: int) -> list[dict[str, str]]:
    """Choose one image per patient, preserving a random test-split sample.

    One image per patient prevents near-duplicate follow-up studies from making
    the classroom sample look stronger than it is.  A fixed seed makes the
    sample reproducible.  The guard verifies that every planned pathology is
    represented when that pathology exists in the source test split.
    """
    by_patient: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_patient.setdefault(row[PATIENT_COLUMN], []).append(row)
    if count > len(by_patient):
        raise ValueError(f"Requested {count} images but the test split has only {len(by_patient)} patients.")

    rng = random.Random(seed)
    candidates = []
    for patient_rows in by_patient.values():
        candidates.append(rng.choice(patient_rows))
    rng.shuffle(candidates)
    selected = candidates[:count]

    source_labels = Counter(label for row in rows for label in parse_labels(row[LABEL_COLUMN]))
    selected_labels = Counter(label for row in selected for label in parse_labels(row[LABEL_COLUMN]))
    missing = [label for label in DEFAULT_LABELS if source_labels[label] and not selected_labels[label]]
    for label in missing:
        replacement = next(row for row in candidates[count:] if label in parse_labels(row[LABEL_COLUMN]))
        replace_at = next(
            index for index, row in enumerate(selected)
            if all(selected_labels[item] > 1 for item in parse_labels(row[LABEL_COLUMN]) if item in DEFAULT_LABELS)
        )
        old = selected[replace_at]
        for item in parse_labels(old[LABEL_COLUMN]):
            selected_labels[item] -= 1
        selected[replace_at] = replacement
        for item in parse_labels(replacement[LABEL_COLUMN]):
            selected_labels[item] += 1
    return sorted(selected, key=lambda row: row[IMAGE_COLUMN])


def resolve_image(row: dict[str, str], data_root: Path) -> Path:
    raw_path = Path(row["image_path"])
    candidates = [raw_path, data_root / raw_path.name, data_root / "images" / raw_path.name]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Cannot locate {row[IMAGE_COLUMN]}; tried: {', '.join(map(str, candidates))}")


def write_csv(path: Path, rows: Iterable[dict[str, str]]) -> None:
    fields = [IMAGE_COLUMN, LABEL_COLUMN, PATIENT_COLUMN, VIEW_COLUMN, "image_path", "sha256"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_dataset(
    manifest_path: Path,
    splits_path: Path,
    data_root: Path,
    output_dir: Path,
    count: int = 600,
    seed: int = 60,
    create_zip: bool = False,
) -> Path:
    if output_dir.exists():
        raise FileExistsError(f"Output already exists: {output_dir}. Choose a new directory or remove it first.")
    rows = select_rows(load_test_rows(manifest_path, splits_path), count, seed)
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True)
    output_rows: list[dict[str, str]] = []
    label_counts: Counter[str] = Counter()
    for row in rows:
        source = resolve_image(row, data_root)
        destination = images_dir / source.name
        shutil.copy2(source, destination)
        labels = parse_labels(row[LABEL_COLUMN])
        label_counts.update(labels)
        output_rows.append({
            IMAGE_COLUMN: row[IMAGE_COLUMN],
            LABEL_COLUMN: row[LABEL_COLUMN],
            PATIENT_COLUMN: row[PATIENT_COLUMN],
            VIEW_COLUMN: row[VIEW_COLUMN],
            "image_path": str(Path("images") / source.name),
            "sha256": row.get("sha256", ""),
        })
    write_csv(output_dir / "manifest.csv", output_rows)
    (output_dir / "splits.json").write_text(
        json.dumps({"train": [], "val": [], "test": [row[IMAGE_COLUMN] for row in output_rows]}, indent=2),
        encoding="utf-8",
    )
    card = {
        "name": "NEO RX - conjunto de demostracion NIH ChestX-ray14",
        "purpose": "Demostracion tecnica del flujo de inferencia; no es un conjunto clinico de la empresa.",
        "source": "NIH ChestX-ray14, subconjunto del split test del entrenamiento Kaggle.",
        "selection": {"split": "test", "images": len(output_rows), "unique_patients": len({row[PATIENT_COLUMN] for row in rows}), "seed": seed},
        "labels": dict(sorted(label_counts.items())),
        "warning": "No usar para diagnostico clinico ni para volver a ajustar el modelo. El rendimiento final debe validarse con un conjunto externo revisado por radiologia.",
    }
    (output_dir / "dataset_card.json").write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "README.md").write_text(
        "# Conjunto de demostracion NEO RX\n\n"
        "Contiene una muestra reproducible de imagenes del split `test` de NIH ChestX-ray14. "
        "Las imagenes no participaron en el entrenamiento ni en el ajuste de hiperparametros.\n\n"
        "- `images/`: radiografias PNG.\n"
        "- `manifest.csv`: etiquetas de referencia y trazabilidad.\n"
        "- `dataset_card.json`: origen, semilla y distribucion.\n\n"
        "Es una evidencia academica del flujo de IA. No equivale a un dataset de pacientes de la empresa ni habilita uso clinico.\n",
        encoding="utf-8",
    )
    if create_zip:
        archive = output_dir.with_suffix(".zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for file_path in output_dir.rglob("*"):
                if file_path.is_file():
                    bundle.write(file_path, file_path.relative_to(output_dir.parent))
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a small NIH test-split demonstration dataset.")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--seed", type=int, default=60)
    parser.add_argument("--zip", action="store_true", help="Also create output-dir.zip")
    args = parser.parse_args()
    if not 1 <= args.count <= 600:
        parser.error("--count must be between 1 and 600 for the demonstration set")
    result = build_dataset(
        manifest_path=args.manifest,
        splits_path=args.splits,
        data_root=args.data_root,
        output_dir=args.output_dir,
        count=args.count,
        seed=args.seed,
        create_zip=args.zip,
    )
    print(f"Created {args.count} held-out test images at {result}")


if __name__ == "__main__":
    main()
