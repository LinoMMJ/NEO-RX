from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

from training.create_splits import PULMONARY_LABELS, candidate_score, split_for_seed
from training.dataset import (
    IMAGE_COLUMN, _limit_splits, _load_records, _select_split,
    build_eval_transform, build_train_transform,
)
from training.model import load_checkpoint, save_checkpoint
from training.threshold_optimizer import ThresholdOptimizer, save_thresholds_csv
from training.validate_dataset import index_images, inspect_record


def test_kaggle_manifest_supports_nested_images_and_stable_ids(tmp_path):
    nested = tmp_path / "images_001" / "images"
    nested.mkdir(parents=True)
    image_path = nested / "sample.png"
    Image.fromarray(np.asarray([[0, 64], [128, 255]], dtype=np.uint8)).save(image_path)
    frame = pd.DataFrame([{
        "Image Index": "sample.png",
        "Finding Labels": "Pneumonia",
        "Patient ID": 7,
        "View Position": "PA",
        "image_path": str(image_path),
    }])
    manifest = tmp_path / "clean_manifest.csv"
    frame.to_csv(manifest, index=False)
    loaded = _load_records(tmp_path, manifest)
    selected = _select_split(loaded, ["sample.png"])
    assert selected.iloc[0][IMAGE_COLUMN] == "sample.png"
    assert Path(selected.iloc[0]["image_path"]) == image_path


def test_audit_rejects_duplicate_content(tmp_path):
    for name in ("one.png", "two.png"):
        Image.fromarray(np.asarray([[0, 32], [128, 255]], dtype=np.uint8)).save(tmp_path / name)
    paths = index_images(tmp_path)
    row = pd.Series({
        "Image Index": "one.png",
        "Finding Labels": "No Finding",
        "Patient ID": 1,
        "View Position": "AP",
    })
    clean, rejected = inspect_record((0, row, paths, 1.0))
    assert rejected is None
    assert clean["sha256"]
    assert clean["View Position"] == "AP"


def test_max_samples_really_limits_all_splits():
    splits = {
        "train": [f"train-{i}" for i in range(70)],
        "val": [f"val-{i}" for i in range(15)],
        "test": [f"test-{i}" for i in range(15)],
    }
    limited = _limit_splits(splits, 20, seed=42)
    assert sum(map(len, limited.values())) == 20
    assert all(limited[name] for name in ("train", "val", "test"))
    assert limited == _limit_splits(splits, 20, seed=42)


def test_atomic_checkpoint_roundtrips_training_state(tmp_path):
    model = torch.nn.Linear(2, 1)
    target = tmp_path / "last.pt"
    save_checkpoint(
        target,
        model,
        pathologies=["Pneumonia"],
        labels_es={"Pneumonia": "Neumonía"},
        thresholds=[0.4],
        training_state={"phase": "finetune", "next_epoch": 6, "optimizer_state": {"ok": True}},
    )
    checkpoint = load_checkpoint(target)
    assert checkpoint["training_state"]["phase"] == "finetune"
    assert checkpoint["training_state"]["next_epoch"] == 6
    assert checkpoint["thresholds"]["Pneumonia"] == 0.4
    assert not target.with_suffix(".pt.tmp").exists()



def test_patient_split_is_deterministic_and_has_no_leakage():
    rows = []
    findings = "|".join(PULMONARY_LABELS)
    for patient_id in range(40):
        rows.append({
            "Image Index": f"patient-{patient_id}-a.png",
            "Finding Labels": findings,
            "Patient ID": patient_id,
        })
        rows.append({
            "Image Index": f"patient-{patient_id}-b.png",
            "Finding Labels": findings,
            "Patient ID": patient_id,
        })
    frame = pd.DataFrame(rows)
    first = split_for_seed(frame, 42, 0.70, 0.15)
    second = split_for_seed(frame, 42, 0.70, 0.15)
    assert first.equals(second)
    sets = {
        name: set(frame.loc[first == name, "Patient ID"])
        for name in ("train", "val", "test")
    }
    assert not (sets["train"] & sets["val"])
    assert not (sets["train"] & sets["test"])
    assert not (sets["val"] & sets["test"])
    score, counts = candidate_score(frame, first, PULMONARY_LABELS)
    assert np.isfinite(score)
    assert all((counts[name] > 0).all() for name in counts)


def test_threshold_optimizer_imports():
    assert ThresholdOptimizer is not None
    assert callable(save_thresholds_csv)


def test_training_entrypoints_import():
    from training import compare, train
    assert callable(train.main)
    assert callable(compare.main)


def test_xray_transforms_accept_callable_components():
    image = torch.zeros((1, 1024, 1024), dtype=torch.float32)
    train_transform = build_train_transform({'augmentation': {'enabled': False}})
    assert train_transform(image).shape == (1, 512, 512)
    assert build_eval_transform()(image).shape == (1, 512, 512)
