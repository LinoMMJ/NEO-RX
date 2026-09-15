"""
NIH ChestX-ray14 Dataset Preparation

Downloads dataset via Kaggle (or validates local copy), creates patient-level
train/val/test splits (70/15/15) to avoid data leakage, and saves splits.json.

Usage:
    python -m training.prepare_dataset --data-dir data/nih --source kaggle
    python -m training.prepare_dataset --data-dir data/nih --source local
"""

import argparse
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split


NIH_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Effusion",
    "Fibrosis",
    "Hernia",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
]

NIH_LABEL_SET = set(NIH_LABELS)

REQUIRED_COLUMNS = ["Image Index", "Finding Labels", "Patient ID"]


def parse_args():
    parser = argparse.ArgumentParser(description="Prepare NIH ChestX-ray14 dataset")
    parser.add_argument(
        "--data-dir",
        type=Path,
        required=True,
        help="Target directory for dataset (will contain images/ and Data_Entry_2017.csv)",
    )
    parser.add_argument(
        "--source",
        choices=["kaggle", "local"],
        required=True,
        help="Source of dataset: 'kaggle' to download via kagglehub, 'local' to validate existing",
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.7,
        help="Train split ratio (default: 0.7)",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Validation split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--test-ratio",
        type=float,
        default=0.15,
        help="Test split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum total samples across all splits (creates balanced subset). Default: use all.",
    )
    parser.add_argument(
        "--stratify",
        action="store_true",
        help="Balance classes in subset using stratified sampling per class (with --max-samples).",
    )
    return parser.parse_args()


def download_kaggle_dataset(target_dir: Path) -> Path:
    """Download NIH ChestX-ray14 via kagglehub and extract to target_dir."""
    try:
        import kagglehub
    except ImportError:
        sys.exit("kagglehub not installed. Run: pip install kagglehub")

    print("Downloading NIH ChestX-ray14 via kagglehub...")
    # kagglehub returns the path to the downloaded dataset
    dataset_path = Path(kagglehub.dataset_download("nih-chest-xrays/data"))
    print(f"Downloaded to: {dataset_path}")

    # The dataset structure varies; find images and CSV
    csv_files = list(dataset_path.rglob("Data_Entry_2017.csv"))
    if not csv_files:
        csv_files = list(dataset_path.rglob("*.csv"))
    if not csv_files:
        sys.exit("Could not find Data_Entry_2017.csv in downloaded dataset")

    csv_src = csv_files[0]
    print(f"Found CSV: {csv_src}")

    # Find images directory (usually images_001, images_002, ... or just images/)
    img_dirs = [d for d in dataset_path.rglob("images*") if d.is_dir()]
    if not img_dirs:
        # Maybe flat structure
        img_dirs = [d for d in dataset_path.iterdir() if d.is_dir() and any(d.glob("*.png"))]
    if not img_dirs:
        sys.exit("Could not find images directory in downloaded dataset")

    # Copy to target_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    images_target = target_dir / "images"
    if images_target.exists():
        shutil.rmtree(images_target)

    print(f"Consolidating images to {images_target}...")
    images_target.mkdir(parents=True)

    for img_dir in img_dirs:
        for img_file in img_dir.glob("*.png"):
            shutil.copy2(img_file, images_target / img_file.name)
        for img_file in img_dir.glob("*.jpg"):
            shutil.copy2(img_file, images_target / img_file.name)

    shutil.copy2(csv_src, target_dir / "Data_Entry_2017.csv")

    print(f"Dataset prepared at {target_dir}")
    return target_dir


def validate_local_dataset(data_dir: Path) -> bool:
    """Validate that local dataset has required structure."""
    images_dir = data_dir / "images"
    csv_file = data_dir / "Data_Entry_2017.csv"

    if not images_dir.exists() or not images_dir.is_dir():
        print(f"ERROR: Missing images directory at {images_dir}")
        return False
    if not csv_file.exists():
        print(f"ERROR: Missing Data_Entry_2017.csv at {csv_file}")
        return False

    # Quick check: at least some images
    img_count = len(list(images_dir.glob("*.png"))) + len(list(images_dir.glob("*.jpg")))
    if img_count == 0:
        print(f"ERROR: No images found in {images_dir}")
        return False

    print(f"Local dataset validated: {img_count} images, CSV at {csv_file}")
    return True


def parse_finding_labels(finding_str: str) -> list:
    """Parse 'Atelectasis|Consolidation|No Finding' into list of labels."""
    if pd.isna(finding_str):
        return []
    labels = [l.strip() for l in finding_str.split("|")]
    return [l for l in labels if l in NIH_LABEL_SET]


def create_patient_splits(df: pd.DataFrame, train_ratio: float, val_ratio: float, test_ratio: float, seed: int):
    """Create patient-level splits to avoid data leakage."""
    # Get unique patients
    patients = df["Patient ID"].unique()
    print(f"Total unique patients: {len(patients)}")

    # Split patients (not images!)
    train_patients, temp_patients = train_test_split(
        patients, train_size=train_ratio, random_state=seed, shuffle=True
    )
    # Remaining: val + test
    val_size = val_ratio / (val_ratio + test_ratio)
    val_patients, test_patients = train_test_split(
        temp_patients, train_size=val_size, random_state=seed, shuffle=True
    )

    print(f"Train patients: {len(train_patients)}")
    print(f"Val patients:   {len(val_patients)}")
    print(f"Test patients:  {len(test_patients)}")

    # Map image indices to splits
    patient_to_split = {}
    for p in train_patients:
        patient_to_split[p] = "train"
    for p in val_patients:
        patient_to_split[p] = "val"
    for p in test_patients:
        patient_to_split[p] = "test"

    df["split"] = df["Patient ID"].map(patient_to_split)

    # Verify no overlap
    splits = df.groupby("split")["Patient ID"].nunique()
    print("\nSplit patient counts:")
    print(splits)

    # Class balance per split
    for split_name in ["train", "val", "test"]:
        split_df = df[df["split"] == split_name]
        print(f"\n--- {split_name.upper()} class distribution ---")
        for label in NIH_LABELS:
            count = split_df["labels"].apply(lambda x: label in x).sum()
            total = len(split_df)
            pct = 100 * count / total if total > 0 else 0
            print(f"  {label}: {count}/{total} ({pct:.1f}%)")

    # Return indices per split
    return {
        "train": df[df["split"] == "train"].index.tolist(),
        "val": df[df["split"] == "val"].index.tolist(),
        "test": df[df["split"] == "test"].index.tolist(),
    }


def apply_stratified_subsampling(df: pd.DataFrame, splits: Dict[str, List[int]], max_samples: int, seed: int) -> Dict[str, List[int]]:
    """
    Apply stratified subsampling to get balanced subset while preserving patient-level splits.

    Strategy:
    1. Calculate target samples per class = max_samples / num_classes (roughly)
    2. Within each split, sample up to target per class
    3. Ensure patient-level integrity (all images of a patient stay in same split)
    """
    print(f"\nApplying stratified subsampling (max {max_samples} total samples)...")

    # For each split, collect patient IDs and their class memberships
    new_splits = {"train": [], "val": [], "test": []}

    for split_name in ["train", "val", "test"]:
        split_indices = splits[split_name]
        split_df = df.loc[split_indices].copy()

        # Group by patient
        patient_groups = split_df.groupby("Patient ID")

        # For each class, collect patients that have this class
        class_to_patients = {label: [] for label in NIH_LABELS}
        for pid, group in patient_groups:
            # Get all labels for this patient
            patient_labels = set()
            for _, row in group.iterrows():
                patient_labels.update(row["labels"])
            for label in patient_labels:
                if label in class_to_patients:
                    class_to_patients[label].append(pid)

        # Target per class per split (proportional to split size)
        split_total = len(split_indices)
        split_ratio = split_total / len(df)
        target_per_class = max(1, int((max_samples * split_ratio) / len(NIH_LABELS)))

        # Sample patients per class
        selected_patients = set()
        rng = np.random.RandomState(seed)

        for label in NIH_LABELS:
            patients_with_label = class_to_patients[label]
            if not patients_with_label:
                continue
            # Shuffle and take up to target
            rng.shuffle(patients_with_label)
            for pid in patients_with_label[:target_per_class]:
                selected_patients.add(pid)

        # Also add some "No Finding" patients for negative class balance
        # Patients with NO nih labels
        no_finding_patients = [pid for pid, group in patient_groups if not any(l in NIH_LABEL_SET for _, row in group.iterrows() for l in row["labels"])]
        if no_finding_patients:
            rng.shuffle(no_finding_patients)
            neg_target = max(1, int(target_per_class * 0.3))  # ~30% negatives
            for pid in no_finding_patients[:neg_target]:
                selected_patients.add(pid)

        # Collect all indices for selected patients
        for pid in selected_patients:
            patient_indices = split_df[split_df["Patient ID"] == pid].index.tolist()
            new_splits[split_name].extend(patient_indices)

    # Print final stats
    total_new = sum(len(v) for v in new_splits.values())
    print(f"Subsampled total: {total_new} images (target: {max_samples})")
    for split_name in ["train", "val", "test"]:
        split_df = df.loc[new_splits[split_name]]
        print(f"  {split_name}: {len(split_df)} images")
        for label in NIH_LABELS:
            count = split_df["labels"].apply(lambda x: label in x).sum()
            pct = 100 * count / len(split_df) if len(split_df) > 0 else 0
            print(f"    {label}: {count} ({pct:.1f}%)")

    return new_splits


def main():
    args = parse_args()
    data_dir = Path(args.data_dir).resolve()

    # Download or validate
    if args.source == "kaggle":
        download_kaggle_dataset(data_dir)
    else:
        if not validate_local_dataset(data_dir):
            sys.exit(1)

    # Load CSV
    csv_path = data_dir / "Data_Entry_2017.csv"
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path)

    # Validate columns
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        sys.exit(f"CSV missing required columns: {missing}")

    print(f"Loaded {len(df)} rows")

    # Parse labels
    df["labels"] = df["Finding Labels"].apply(parse_finding_labels)

    # Overall class distribution
    print("\n--- Overall class distribution ---")
    for label in NIH_LABELS:
        count = df["labels"].apply(lambda x: label in x).sum()
        pct = 100 * count / len(df)
        print(f"  {label}: {count}/{len(df)} ({pct:.1f}%)")

    # Create patient-level splits
    print("\nCreating patient-level splits...")
    splits = create_patient_splits(
        df, args.train_ratio, args.val_ratio, args.test_ratio, args.seed
    )

    # Apply stratified subsampling if requested
    if args.max_samples and args.stratify:
        splits = apply_stratified_subsampling(df, splits, args.max_samples, args.seed)

    # Save splits
    splits_json = data_dir / "splits.json"
    with open(splits_json, "w") as f:
        json.dump(splits, f, indent=2)

    print(f"\nSplits saved to {splits_json}")
    print(f"Train: {len(splits['train'])} images")
    print(f"Val:   {len(splits['val'])} images")
    print(f"Test:  {len(splits['test'])} images")

    # Also save labels list for reference
    labels_json = data_dir / "labels.json"
    with open(labels_json, "w") as f:
        json.dump(NIH_LABELS, f, indent=2)
    print(f"Labels saved to {labels_json}")


if __name__ == "__main__":
    main()