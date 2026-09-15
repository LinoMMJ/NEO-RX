"""
Neo RX — Fine-tuning Pipeline for Chest X-ray Classification.

This package provides utilities to download, prepare, train, evaluate, and compare
a fine-tuned ResNet-50 model on the NIH ChestX-ray14 dataset.

Usage:
    1. Prepare dataset:     python -m training.prepare_dataset --data-dir data/nih --source kaggle
    2. Train model:         python -m training.train --config training/config.yaml
    3. Evaluate model:      python -m training.evaluate --config training/config.yaml --checkpoint checkpoints/finetuned_resnet50_nih.pt
    4. Compare with baseline: python -m training.compare --config training/config.yaml
"""

__version__ = "1.0.0"