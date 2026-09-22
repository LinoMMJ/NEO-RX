"""Dataset and DataLoader helpers for local and Kaggle NIH ChestX-ray14 runs.

The Kaggle input mount is read-only and its images can be spread over multiple
folders. A validated manifest therefore acts as the source of truth.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
import torchxrayvision as xrv
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms as T

IMAGE_COLUMN = "Image Index"
LABEL_COLUMN = "Finding Labels"
PATIENT_COLUMN = "Patient ID"
VIEW_COLUMN = "View Position"


def parse_finding_labels(finding_str: str, label_set: set) -> List[str]:
    if pd.isna(finding_str):
        return []
    return [label.strip() for label in str(finding_str).split("|") if label.strip() in label_set]


class GaussianNoise(torch.nn.Module):
    def __init__(self, std: float = 0.01):
        super().__init__()
        self.std = std

    def forward(self, tensor: torch.Tensor) -> torch.Tensor:
        return tensor + torch.randn_like(tensor) * self.std if self.training and self.std > 0 else tensor


def build_train_transform(cfg: Dict) -> T.Compose:
    aug = cfg.get("augmentation", {})
    items = []
    if aug.get("enabled", True):
        rotation = aug.get("rotation_degrees", 5)
        if rotation:
            items.append(T.RandomRotation(rotation, fill=-1024))
        scale = aug.get("scale_range", 0.10)
        if scale:
            items.append(T.RandomAffine(0, translate=(0.05, 0.05), scale=(1 - scale, 1 + scale), fill=-1024))
        brightness, contrast = aug.get("brightness", 0.15), aug.get("contrast", 0.15)
        if brightness or contrast:
            items.append(T.ColorJitter(brightness=brightness, contrast=contrast))
        noise = aug.get("gaussian_noise_std", 0.01)
        if noise:
            items.append(GaussianNoise(noise))
    items.extend([xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(512)])
    return T.Compose(items)


def build_eval_transform() -> T.Compose:
    return T.Compose([xrv.datasets.XRayCenterCrop(), xrv.datasets.XRayResizer(512)])


def _resolve_path(path_value: str, manifest_path: Optional[Path], data_dir: Path) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    candidates = []
    if manifest_path:
        candidates.append(manifest_path.parent / path)
    candidates.extend([data_dir / path, data_dir / "images" / path.name])
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def _load_records(data_dir: Path, manifest_path: Optional[Path]) -> pd.DataFrame:
    if manifest_path:
        frame = pd.read_csv(manifest_path)
        required = {IMAGE_COLUMN, LABEL_COLUMN, PATIENT_COLUMN, "image_path"}
    else:
        frame = pd.read_csv(data_dir / "Data_Entry_2017.csv")
        required = {IMAGE_COLUMN, LABEL_COLUMN, PATIENT_COLUMN}
        frame["image_path"] = frame[IMAGE_COLUMN].map(lambda name: str(data_dir / "images" / str(name)))
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Dataset metadata is missing columns: {missing}")
    frame[IMAGE_COLUMN] = frame[IMAGE_COLUMN].astype(str)
    if frame[IMAGE_COLUMN].duplicated().any():
        raise ValueError("Image Index must be unique after dataset validation")
    frame["image_path"] = frame["image_path"].map(
        lambda value: str(_resolve_path(str(value), manifest_path, data_dir))
    )
    return frame


def _select_split(frame: pd.DataFrame, values: Sequence) -> pd.DataFrame:
    if not values:
        return frame.iloc[0:0].copy()
    if isinstance(values[0], str):
        indexed = frame.set_index(IMAGE_COLUMN, drop=False)
        missing = [value for value in values if value not in indexed.index]
        if missing:
            raise ValueError(f"Split references {len(missing)} images absent from the clean manifest")
        return indexed.loc[list(values)].reset_index(drop=True)
    return frame.iloc[list(values)].reset_index(drop=True)


def _limit_splits(splits: Dict[str, List], maximum: Optional[int], seed: int) -> Dict[str, List]:
    if not maximum:
        return splits
    if maximum < 3:
        raise ValueError("--max-samples must be at least 3")
    total = sum(len(values) for values in splits.values())
    if maximum >= total:
        return splits
    rng = np.random.default_rng(seed)
    result, remaining = {}, maximum
    names = ("train", "val", "test")
    for index, name in enumerate(names):
        values = list(splits[name])
        if index == len(names) - 1:
            count = min(len(values), remaining)
        else:
            count = min(len(values), max(1, round(maximum * len(values) / total)))
            remaining -= count
        chosen = rng.choice(len(values), size=count, replace=False)
        result[name] = [values[int(i)] for i in sorted(chosen)]
    return result


class NIHDataset(Dataset):
    def __init__(self, frame: pd.DataFrame, labels: List[str], transform=None):
        self.df = frame.reset_index(drop=True).copy()
        self.labels = labels
        self.label_to_idx = {label: index for index, label in enumerate(labels)}
        self.df["labels"] = self.df[LABEL_COLUMN].apply(lambda value: parse_finding_labels(value, set(labels)))
        self.transform = transform

    def __len__(self) -> int:
        return len(self.df)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor, str]:
        row = self.df.iloc[idx]
        image_path = Path(row["image_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Image not found: {image_path}")
        with Image.open(image_path) as image:
            array = np.asarray(image.convert("L"), dtype=np.float32)
        array = xrv.datasets.normalize(array, 255.0)
        tensor = torch.from_numpy(array[None, :, :] if array.ndim == 2 else array)
        if self.transform is not None:
            tensor = self.transform(tensor)
        target = torch.zeros(len(self.labels), dtype=torch.float32)
        for label in row["labels"]:
            target[self.label_to_idx[label]] = 1.0
        return tensor, target, str(row[IMAGE_COLUMN])


def get_dataloaders(
    cfg: Dict,
    splits_json: Path,
    data_dir: Path,
    max_samples: Optional[int] = None,
) -> Tuple[DataLoader, DataLoader, DataLoader]:
    with open(splits_json, encoding="utf-8") as handle:
        splits = _limit_splits(json.load(handle), max_samples, cfg["train"].get("seed", 42))
    manifest_value = cfg.get("data", {}).get("manifest")
    manifest_path = Path(manifest_value) if manifest_value else None
    frame = _load_records(Path(data_dir), manifest_path)
    labels = cfg.get("pulmonary_labels", cfg.get("nih_labels", []))
    train = NIHDataset(_select_split(frame, splits["train"]), labels, build_train_transform(cfg))
    val = NIHDataset(_select_split(frame, splits["val"]), labels, build_eval_transform())
    test = NIHDataset(_select_split(frame, splits["test"]), labels, build_eval_transform())
    batch_size = cfg["train"]["batch_size"]
    workers = cfg["train"]["num_workers"]
    common = dict(batch_size=batch_size, num_workers=workers, pin_memory=torch.cuda.is_available(),
                  persistent_workers=workers > 0, drop_last=False)
    return (
        DataLoader(train, shuffle=True, **common),
        DataLoader(val, shuffle=False, **common),
        DataLoader(test, shuffle=False, **common),
    )
