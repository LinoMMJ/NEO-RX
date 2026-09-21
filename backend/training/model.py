"""
Model Building, Checkpoint Save/Load for Fine-tuning

Provides:
- build_model(): Creates torchxrayvision ResNet with swapped head
- Freeze/unfreeze helpers for two-stage training
- save_checkpoint() / load_checkpoint() with metadata including thresholds and pos_weight

IMPORTANT: All metrics are PENDIENTE DE EJECUCIÓN EXPERIMENTAL.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torchxrayvision as xrv


# Default NIH labels (for reference/backward compatibility)
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

# Pulmonary-only labels (12 classes, excludes Cardiomegaly, Hernia)
PULMONARY_LABELS: List[str] = [
    "Atelectasis",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Effusion",
    "Fibrosis",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
]


def build_model(cfg: Dict) -> xrv.models.ResNet:
    """
    Build torchxrayvision ResNet with new classification head.

    Args:
        cfg: Config dict with 'model' key containing:
            - base_weights: str (e.g., "resnet50-res512-all")
            - num_classes: int (12 for pulmonary labels)

    Returns:
        xrv.models.ResNet with:
            - model.model.fc = nn.Linear(2048, num_classes)
            - model.pathologies = configured labels
            - model.op_norm = nn.Sigmoid() (preserved from xrv)
    """
    base_weights = cfg["model"]["base_weights"]
    num_classes = cfg["model"]["num_classes"]

    # Load pretrained xrv model (includes op_norm=Sigmoid in forward)
    model = xrv.models.ResNet(weights=base_weights)

    # Replace classification head: xrv stores torchvision resnet in .model
    # model.model.fc is the final Linear layer
    in_features = model.model.fc.in_features  # 2048 for ResNet-50
    model.model.fc = nn.Linear(in_features, num_classes)

    # Set pathologies list from config (or default to pulmonary)
    labels = cfg.get("pulmonary_labels", cfg.get("nih_labels", PULMONARY_LABELS))
    model.pathologies = labels.copy()

    return model


def set_head_only(model: xrv.models.ResNet, freeze: bool = True) -> None:
    """
    Freeze/unfreeze all params except the new head (model.model.fc).

    Args:
        model: xrv.models.ResNet
        freeze: True to freeze backbone, False to unfreeze all
    """
    # Freeze everything first
    for param in model.parameters():
        param.requires_grad = not freeze

    # Always unfreeze the new head
    for param in model.model.fc.parameters():
        param.requires_grad = True

    # Ensure op_norm (Sigmoid) params are not frozen (no params anyway)
    # model.op_norm is nn.Sigmoid() — no parameters


def unfreeze_partial(model: xrv.models.ResNet) -> None:
    """
    Unfreeze layer3, layer4, and fc for partial fine-tuning.

    Keeps layer1, layer2, conv1, bn1 frozen.
    """
    # Unfreeze layer3 and layer4
    for name, param in model.model.named_parameters():
        if "layer3" in name or "layer4" in name or "fc" in name:
            param.requires_grad = True
        else:
            param.requires_grad = False

    # Head always trainable
    for param in model.model.fc.parameters():
        param.requires_grad = True


def count_trainable_params(model: nn.Module) -> Tuple[int, int]:
    """Return (trainable_params, total_params)."""
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    return trainable, total


def save_checkpoint(
    path: Path,
    model: xrv.models.ResNet,
    pathologies: List[str],
    labels_es: Dict[str, str],
    metrics: Optional[Dict] = None,
    extra: Optional[Dict] = None,
    thresholds: Optional[List[float]] = None,
    pos_weight: Optional[List[float]] = None,
    training_state: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Save model checkpoint with full metadata for inference integration.

    Args:
        path: Output .pt file path
        model: Trained xrv.models.ResNet
        pathologies: List of EN label names (order matches model head)
        labels_es: EN -> ES mapping
        metrics: Optional dict with AUC, etc.
        extra: Any extra metadata (e.g., config, date, git hash)
        thresholds: Optional list of optimal thresholds per class (from validation)
        pos_weight: Optional list of pos_weight values per class (from train split)
        training_state: Optimizer/scheduler/scaler/RNG state for exact resume.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    checkpoint = {
        "state_dict": model.state_dict(),
        "pathologies": pathologies,
        "labels_es": labels_es,
        "num_classes": len(pathologies),
        "model_arch": "resnet50",
        "base_weights": "resnet50-res512-all",
        "pulmonary_labels": [l for l in pathologies if l not in ("Cardiomegaly", "Hernia")],
    }

    # Add thresholds if provided (from validation optimization)
    if thresholds is not None:
        # Ensure thresholds match pathologies order
        if isinstance(thresholds, dict):
            threshold_dict = {label: float(thresholds[label]) for label in pathologies}
        else:
            threshold_dict = {label: float(thr) for label, thr in zip(pathologies, thresholds)}
        checkpoint["thresholds"] = threshold_dict
        checkpoint["thresholds_list"] = [threshold_dict[label] for label in pathologies]

    # Add pos_weight if provided (calculated from TRAIN split)
    if pos_weight is not None:
        checkpoint["pos_weight"] = [float(w) for w in pos_weight]

    if metrics:
        checkpoint["metrics"] = metrics
    if extra:
        checkpoint["extra"] = extra
    if training_state:
        checkpoint["training_state"] = training_state

    # Add timestamp
    from datetime import datetime, timezone
    checkpoint["saved_at"] = datetime.now(timezone.utc).isoformat()

    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(checkpoint, temporary, _use_new_zipfile_serialization=True)
    temporary.replace(path)
    print(f"Checkpoint saved atomically to {path}")


def load_checkpoint(path: Path) -> Dict[str, Any]:
    """
    Load checkpoint dict.

    Returns dict with keys: state_dict, pathologies, labels_es, metrics, thresholds, pos_weight, etc.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Checkpoint not found: {path}")

    # weights_only=False required because checkpoint contains lists/dicts (metadata)
    checkpoint = torch.load(path, map_location="cpu", weights_only=False)
    return checkpoint


def load_finetuned_model(
    checkpoint_path: Path,
    base_weights: str = "resnet50-res512-all",
) -> xrv.models.ResNet:
    """
    Load fine-tuned model from checkpoint, ready for inference.

    This is the function DetectorTorax.cargar() should call when
    NEORX_MODEL_PATH is set.

    Args:
        checkpoint_path: Path to .pt file from save_checkpoint()
        base_weights: Base architecture weights (used to instantiate structure)

    Returns:
        xrv.models.ResNet with loaded weights, correct head size, and pathologies set.
    """
    ckpt = load_checkpoint(checkpoint_path)
    pathologies = ckpt["pathologies"]
    num_classes = len(pathologies)

    # Instantiate base model (weights will be overwritten)
    model = xrv.models.ResNet(weights=base_weights)

    # Replace head to match checkpoint
    in_features = model.model.fc.in_features
    model.model.fc = nn.Linear(in_features, num_classes)

    # Load state dict (includes fc + op_norm + backbone)
    state_dict = ckpt["state_dict"] if "state_dict" in ckpt else ckpt
    model.load_state_dict(state_dict, strict=True)

    # Set pathologies for metadata
    model.pathologies = pathologies

    # Attach thresholds if available (for inference use)
    if "thresholds" in ckpt:
        model.thresholds = ckpt["thresholds"]
    elif "thresholds_list" in ckpt:
        model.thresholds = {label: thr for label, thr in zip(pathologies, ckpt["thresholds_list"])}

    model.eval()
    return model


def get_thresholds_from_checkpoint(checkpoint_path: Path) -> Dict[str, float]:
    """
    Extract thresholds from a checkpoint file.

    Returns:
        Dict mapping label -> threshold
    """
    ckpt = load_checkpoint(checkpoint_path)
    if "thresholds" in ckpt:
        return ckpt["thresholds"]
    elif "thresholds_list" in ckpt:
        pathologies = ckpt["pathologies"]
        return {label: thr for label, thr in zip(pathologies, ckpt["thresholds_list"])}
    return {}


def get_pos_weight_from_checkpoint(checkpoint_path: Path) -> Optional[List[float]]:
    """Extract pos_weight from a checkpoint file."""
    ckpt = load_checkpoint(checkpoint_path)
    return ckpt.get("pos_weight")
