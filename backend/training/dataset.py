"""
NIH ChestX-ray14 PyTorch Dataset and DataLoaders

Provides NIHDataset and get_dataloaders() for training/evaluation.
Uses torchxrayvision transforms for exact preprocessing parity with inference.
"""

from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import torch
import torchxrayvision as xrv
from PIL import Image
from torch.utils.data import DataLoader, Dataset


# Fixed order — must match config.yaml and model checkpoint
NIH_LABELS: List[str] = [
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
LABEL_TO_IDX = {label: i for i, label in enumerate(NIH_LABELS)}


def parse_finding_labels(finding_str: str) -> List[str]:
    """Parse 'Atelectasis|Consolidation|No Finding' into list of NIH labels."""
    if pd.isna(finding_str):
        return []
    labels = [l.strip() for l in finding_str.split("|")]
    return [l for l in labels if l in NIH_LABEL_SET]


class NIHDataset(Dataset):
    """
    PyTorch Dataset for NIH ChestX-ray14.

    Each sample returns:
        - image: Tensor [1, 512, 512] float32, normalized to [-1024, 1024] via xrv.normalize
        - target: Tensor [14] float32, multi-label binary (0/1)
        - index: int, original row index in CSV
    """

    def __init__(
        self,
        csv_path: Path,
        images_dir: Path,
        indices: List[int],
        transform=None,
    ):
        """
        Args:
            csv_path: Path to Data_Entry_2017.csv
            images_dir: Directory containing PNG/JPG images
            indices: List of row indices (from splits.json) to include
            transform: Optional transform (default: xrv XRayCenterCrop + XRayResizer(512))
        """
        self.csv_path = Path(csv_path)
        self.images_dir = Path(images_dir)
        self.indices = indices

        # Load only required rows
        self.df = pd.read_csv(csv_path, usecols=["Image Index", "Finding Labels", "Patient ID"])
        self.df = self.df.iloc[indices].reset_index(drop=True)
        self.df["labels"] = self.df["Finding Labels"].apply(parse_finding_labels)

        # Default transform: matches torchxrayvision inference pipeline
        if transform is None:
            self.transform = torch.nn.Sequential(
                xrv.datasets.XRayCenterCrop(),
                xrv.datasets.XRayResizer(512),
            )
        else:
            self.transform = transform

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, int]:
        row = self.df.iloc[idx]
        img_name = row["Image Index"]
        labels = row["labels"]

        # Load image
        img_path = self.images_dir / img_name
        if not img_path.exists():
            # Try .png if .jpg or vice versa
            alt = img_path.with_suffix(".png" if img_path.suffix == ".jpg" else ".jpg")
            if alt.exists():
                img_path = alt
            else:
                raise FileNotFoundError(f"Image not found: {img_path} (tried {alt})")

        # Open as grayscale float32 [H, W]
        with Image.open(img_path) as img:
            img = img.convert("L")  # force grayscale
            arr = np.array(img, dtype=np.float32)

        # Normalize using xrv convention: maxval=255 for 8-bit PNG
        arr = xrv.datasets.normalize(arr, 255.0)  # -> [-1024, 1024]

        # Apply transform: [H, W] -> [1, 512, 512]
        # xrv transforms expect [C, H, W] or [H, W]; ensure channel dim
        if arr.ndim == 2:
            arr = arr[None, :, :]  # [1, H, W]
        img_tensor = torch.from_numpy(arr)
        img_tensor = self.transform(img_tensor)  # -> [1, 512, 512]

        # Build multi-label target [14]
        target = torch.zeros(len(NIH_LABELS), dtype=torch.float32)
        for label in labels:
            if label in LABEL_TO_IDX:
                target[LABEL_TO_IDX[label]] = 1.0

        original_index = self.indices[idx]
        return img_tensor, target, original_index


def get_dataloaders(
    cfg: Dict,
    splits_json: Path,
    data_dir: Path,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create train/val/test DataLoaders from config and splits.

    Args:
        cfg: Loaded config.yaml dict (with 'data', 'train' keys)
        splits_json: Path to splits.json created by prepare_dataset.py
        data_dir: Root data directory (contains images/ and Data_Entry_2017.csv)

    Returns:
        (train_loader, val_loader, test_loader)
    """
    with open(splits_json) as f:
        splits = json.load(f)

    csv_path = data_dir / "Data_Entry_2017.csv"
    images_dir = data_dir / "images"

    train_ds = NIHDataset(csv_path, images_dir, splits["train"])
    val_ds = NIHDataset(csv_path, images_dir, splits["val"])
    test_ds = NIHDataset(csv_path, images_dir, splits["test"])

    train_loader = DataLoader(
        train_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=True,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=True,
        drop_last=False,
        persistent_workers=cfg["train"]["num_workers"] > 0,
    )
    val_loader = DataLoader(
        val_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=True,
        drop_last=False,
        persistent_workers=cfg["train"]["num_workers"] > 0,
    )
    test_loader = DataLoader(
        test_ds,
        batch_size=cfg["train"]["batch_size"],
        shuffle=False,
        num_workers=cfg["train"]["num_workers"],
        pin_memory=True,
        drop_last=False,
        persistent_workers=cfg["train"]["num_workers"] > 0,
    )

    return train_loader, val_loader, test_loader


# Import json at top level for get_dataloaders
import json