"""Audit NIH ChestX-ray14 without copying Kaggle's read-only input dataset."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Iterable

import numpy as np
import pandas as pd
from PIL import Image, UnidentifiedImageError

REQUIRED = ("Image Index", "Finding Labels", "Patient ID")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg"}


def parse_args():
    parser = argparse.ArgumentParser(description="Validate NIH ChestX-ray14 and create a clean manifest")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--min-std", type=float, default=1.0)
    parser.add_argument("--max-images", type=int, help="Audit only N rows for a smoke test")
    return parser.parse_args()


def find_metadata(root: Path, explicit: Path | None) -> Path:
    if explicit:
        if not explicit.exists():
            raise FileNotFoundError(explicit)
        return explicit
    exact = sorted(root.rglob("Data_Entry_2017.csv"))
    candidates = exact or sorted(root.rglob("*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No metadata CSV found below {root}")
    return candidates[0]


def index_images(root: Path) -> Dict[str, list[Path]]:
    result: Dict[str, list[Path]] = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES:
            result.setdefault(path.name, []).append(path.resolve())
    return result


def inspect_record(item):
    position, row, paths, min_std = item
    name = str(row["Image Index"])
    base = {
        "csv_index": int(position),
        "Image Index": name,
        "Finding Labels": str(row["Finding Labels"]),
        "Patient ID": row["Patient ID"],
        "View Position": str(row.get("View Position", "UNKNOWN")),
    }
    matches = paths.get(name, [])
    if not matches:
        return None, {**base, "reason": "missing_file", "detail": ""}
    if len(matches) > 1:
        return None, {**base, "reason": "ambiguous_filename", "detail": "|".join(map(str, matches))}
    path = matches[0]
    try:
        payload = path.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        with Image.open(io.BytesIO(payload)) as candidate:
            candidate.verify()
        with Image.open(io.BytesIO(payload)) as candidate:
            array = np.asarray(candidate.convert("L"), dtype=np.uint8)
        if array.ndim != 2 or not array.size:
            raise ValueError(f"invalid grayscale shape {array.shape}")
        deviation = float(array.std())
        if deviation < min_std:
            return None, {**base, "reason": "near_constant_image", "detail": f"std={deviation:.4f}"}
        clean = {
            **base,
            "image_path": str(path),
            "sha256": digest,
            "width": int(array.shape[1]),
            "height": int(array.shape[0]),
            "pixel_min": int(array.min()),
            "pixel_max": int(array.max()),
            "pixel_mean": round(float(array.mean()), 4),
            "pixel_std": round(deviation, 4),
        }
        return clean, None
    except (OSError, ValueError, UnidentifiedImageError) as exc:
        return None, {**base, "reason": "invalid_image", "detail": str(exc)[:500]}


def class_counts(frame: pd.DataFrame) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for value in frame["Finding Labels"].fillna(""):
        for label in str(value).split("|"):
            label = label.strip()
            if label:
                counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items()))


def main():
    args = parse_args()
    root = args.input_root.resolve()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    csv_path = find_metadata(root, args.csv)
    metadata = pd.read_csv(csv_path)
    missing = [column for column in REQUIRED if column not in metadata.columns]
    if missing:
        raise ValueError(f"Metadata is missing required columns: {missing}")
    if args.max_images:
        metadata = metadata.head(args.max_images)
    print(f"Metadata: {csv_path}")
    print(f"Rows to audit: {len(metadata):,}")
    paths = index_images(root)
    print(f"Unique image filenames indexed: {len(paths):,}")
    jobs: Iterable = (
        (position, row, paths, args.min_std) for position, (_, row) in enumerate(metadata.iterrows())
    )
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        inspected = list(pool.map(inspect_record, jobs))
    clean_rows = [clean for clean, _ in inspected if clean]
    rejected = [reject for _, reject in inspected if reject]
    seen_hashes: Dict[str, str] = {}
    unique = []
    for row in clean_rows:
        prior = seen_hashes.get(row["sha256"])
        if prior:
            rejected.append({
                "csv_index": row["csv_index"],
                "Image Index": row["Image Index"],
                "Finding Labels": row["Finding Labels"],
                "Patient ID": row["Patient ID"],
                "View Position": row["View Position"],
                "reason": "duplicate_content",
                "detail": prior,
            })
        else:
            seen_hashes[row["sha256"]] = row["Image Index"]
            unique.append(row)
    clean_frame = pd.DataFrame(unique)
    rejected_frame = pd.DataFrame(rejected)
    clean_path = output / "clean_manifest.csv"
    rejected_path = output / "rejected_images.csv"
    clean_frame.to_csv(clean_path, index=False)
    rejected_frame.to_csv(rejected_path, index=False)
    audit = {
        "input_root": str(root),
        "metadata_csv": str(csv_path),
        "rows_audited": int(len(metadata)),
        "accepted": int(len(clean_frame)),
        "rejected": int(len(rejected_frame)),
        "rejection_reasons": rejected_frame["reason"].value_counts().to_dict() if len(rejected_frame) else {},
        "unique_patients": int(clean_frame["Patient ID"].nunique()) if len(clean_frame) else 0,
        "view_positions": clean_frame["View Position"].value_counts().to_dict() if len(clean_frame) else {},
        "class_counts": class_counts(clean_frame) if len(clean_frame) else {},
        "manifest": str(clean_path),
        "rejected_manifest": str(rejected_path),
    }
    with open(output / "dataset_audit.json", "w", encoding="utf-8") as handle:
        json.dump(audit, handle, indent=2, ensure_ascii=False)
    print(json.dumps(audit, indent=2, ensure_ascii=False))
    if not len(clean_frame):
        raise SystemExit("Dataset audit accepted zero images")


if __name__ == "__main__":
    main()
