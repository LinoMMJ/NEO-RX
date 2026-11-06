"""Recalculate validation metrics from the saved NeoRX predictions."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np
import torch
from django.core.management.base import BaseCommand, CommandError
from scipy.stats import rankdata


def roc_auc(targets, scores):
    positive = targets.astype(bool)
    positives = int(positive.sum())
    negatives = int((~positive).sum())
    if not positives or not negatives:
        return float("nan")
    ranks = rankdata(scores)
    return float(
        (ranks[positive].sum() - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def average_precision(targets, scores):
    positive = targets.astype(bool)
    positives = int(positive.sum())
    if not positives:
        return float("nan")
    order = np.argsort(-scores, kind="mergesort")
    ordered = positive[order]
    precision = np.cumsum(ordered) / (np.arange(len(ordered)) + 1)
    return float(precision[ordered].mean())


class Command(BaseCommand):
    help = (
        "Recalcula AUROC y average precision desde las predicciones de VALIDACIÓN "
        "y verifica el hash del checkpoint entrenado."
    )

    def add_arguments(self, parser):
        parser.add_argument("--predictions", type=Path)
        parser.add_argument("--provenance", type=Path)
        parser.add_argument("--checkpoint", type=Path)

    def handle(self, *args, **options):
        root = Path(__file__).resolve().parents[4]
        predictions = (
            options.get("predictions")
            or root / "qa/modelo_entrenado/validation_predictions.npz"
        ).resolve()
        provenance_path = (
            options.get("provenance")
            or root / "qa/modelo_entrenado/provenance.json"
        ).resolve()
        checkpoint = (
            options.get("checkpoint")
            or Path(
                os.environ.get(
                    "NEORX_MODEL_PATH",
                    root / "backend/models/neorx_effusion_categories_resnet50.pt",
                )
            )
        ).resolve()
        for path in (predictions, provenance_path, checkpoint):
            if not path.is_file():
                raise CommandError(f"Archivo requerido no encontrado: {path}")

        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        actual_hash = self._sha256(checkpoint)
        expected_hash = provenance.get("checkpoint_sha256")
        if actual_hash.lower() != str(expected_hash).lower():
            raise CommandError("El SHA-256 del checkpoint no coincide con la evaluación")

        saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
        selected_epoch = int(saved.get("extra", {}).get("epoch", 0)) + 1
        training_metrics = saved.get("metrics", {})
        started = time.perf_counter()
        data = np.load(predictions, allow_pickle=False)
        targets = data["targets"]
        probabilities = data["probabilities"]
        labels = [str(item) for item in data["labels"]]
        if targets.shape != probabilities.shape or targets.shape[1] != len(labels):
            raise CommandError("Las dimensiones de predicciones y etiquetas no coinciden")

        auc_values = []
        ap_values = []
        self.stdout.write("NeoRX - reproducción verificable de VALIDACIÓN")
        self.stdout.write(f"Checkpoint SHA-256: {actual_hash} [OK]")
        self.stdout.write(f"Época seleccionada: {selected_epoch}")
        self.stdout.write("")
        for index, label in enumerate(labels):
            auc = roc_auc(targets[:, index], probabilities[:, index])
            ap = average_precision(targets[:, index], probabilities[:, index])
            auc_values.append(auc)
            ap_values.append(ap)
            done = index + 1
            bar = "=" * (done * 4) + "." * ((len(labels) - done) * 4)
            self.stdout.write(
                f"{done}/{len(labels)} [{bar}] {label:<21} "
                f"val_auc: {auc:.4f} - val_ap: {ap:.4f}"
            )

        elapsed = time.perf_counter() - started
        macro_auc = float(np.nanmean(auc_values))
        macro_ap = float(np.nanmean(ap_values))
        self.stdout.write("")
        self.stdout.write(
            f"{len(targets)}/{len(targets)} [====================] "
            f"{elapsed:.2f}s - val_macro_auc: {macro_auc:.4f} - "
            f"val_macro_ap: {macro_ap:.4f} - "
            f"val_loss: {float(training_metrics.get('val_loss', float('nan'))):.4f}"
        )
        self.stdout.write(f"Checkpoint verificado de la época seleccionada: {selected_epoch}")
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "Fase de validación reproducida - mejor val_macro_auc: "
                f"{macro_auc * 100:.2f}%"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "Cálculo reproducido sobre VALIDACIÓN guardada; no reentrena el modelo "
                "y AUROC no equivale a accuracy."
            )
        )

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
