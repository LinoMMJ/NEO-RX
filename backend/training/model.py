"""
Model Building, Checkpoint Save/Load for Fine-tuning

Provides:
- build_model(): Creates torchxrayvision ResNet with swapped head
- Freeze/unfreeze helpers for two-stage training
- save_checkpoint() / load_checkpoint() with metadata
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torchxrayvision as xrv


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


def build_model(cfg: Dict) -> xrv.models.ResNet:
    """
    Build torchxrayvision ResNet with new classification head.

    Args:
        cfg: Config dict with 'model' key containing:
            - base_weights: str (e.g., "resnet50-res512-all")
            - num_classes: int (14 for NIH)

    Returns:
        xrv.models.ResNet with:
            - model.model.fc = nn.Linear(2048, num_classes)
            - model.pathologies = NIH_LABELS
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

    # Set pathologies list for metadata (used by DetectorTorax at inference)
    model.pathologies = NIH_LABELS.copy()

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

    if metrics:
        checkpoint["metrics"] = metrics
    if extra:
        checkpoint["extra"] = extra

    # Add timestamp
    from datetime import datetime
    checkpoint["saved_at"] = datetime.utcnow().isoformat() + "Z"

    torch.save(checkpoint, path, _use_new_zipfile_serialization=True)
    print(f"Checkpoint saved to {path}")


def load_checkpoint(path: Path) -> Dict[str, Any]:
    """
    Load checkpoint dict.

    Returns dict with keys: state_dict, pathologies, labels_es, metrics, etc.
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

    model.eval()
    return model