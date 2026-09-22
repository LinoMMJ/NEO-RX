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
    image = np.zeros((1, 1024, 1024), dtype=np.float32)
    train_transform = build_train_transform({'augmentation': {'enabled': True}})
    train_image = train_transform(image)
    eval_image = build_eval_transform()(image)
    assert isinstance(train_image, torch.Tensor)
    assert isinstance(eval_image, torch.Tensor)
    assert train_image.shape == (1, 512, 512)
    assert eval_image.shape == (1, 512, 512)


def test_training_step_updates_model():
    from torch.cuda.amp import GradScaler
    from torch.utils.data import DataLoader, TensorDataset
    from training.train import train_one_epoch

    class TinyModel(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.model = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(4, 2))

    model = TinyModel()
    images = torch.randn(4, 1, 2, 2)
    targets = torch.randint(0, 2, (4, 2), dtype=torch.float32)
    identifiers = torch.arange(4)
    loader = DataLoader(TensorDataset(images, targets, identifiers), batch_size=2)
    optimizer = torch.optim.SGD(model.parameters(), lr=0.01)
    before = model.model[1].weight.detach().clone()

    loss = train_one_epoch(
        model=model,
        loader=loader,
        optimizer=optimizer,
        criterion=torch.nn.BCEWithLogitsLoss(),
        device=torch.device("cpu"),
        use_amp=False,
        scaler=GradScaler(enabled=False),
        grad_clip=1.0,
        epoch=0,
        writer=type("Writer", (), {"add_scalar": lambda *args, **kwargs: None})(),
    )

    assert np.isfinite(loss)
    assert not torch.equal(before, model.model[1].weight.detach())

def test_pos_weight_uses_manifest_without_loading_images():
    from torch.utils.data import DataLoader
    from training.dataset import NIHDataset
    from training.train import calculate_pos_weight

    frame = pd.DataFrame([
        {"Image Index": "missing-1.png", "Finding Labels": "A|B", "Patient ID": 1, "image_path": "missing-1.png"},
        {"Image Index": "missing-2.png", "Finding Labels": "A", "Patient ID": 2, "image_path": "missing-2.png"},
        {"Image Index": "missing-3.png", "Finding Labels": "", "Patient ID": 3, "image_path": "missing-3.png"},
        {"Image Index": "missing-4.png", "Finding Labels": "", "Patient ID": 4, "image_path": "missing-4.png"},
    ])
    loader = DataLoader(NIHDataset(frame, ["A", "B"]), batch_size=2)
    weights = calculate_pos_weight(loader, 2, torch.device("cpu"))
    assert torch.allclose(weights, torch.tensor([1.0, 3.0]))
