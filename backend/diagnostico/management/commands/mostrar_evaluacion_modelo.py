"""Print the real saved validation and test metrics for the trained NeoRX model."""

from __future__ import annotations

import json
import os
from pathlib import Path

import torch
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Muestra las métricas reales guardadas del modelo entrenado por NeoRX."

    def add_arguments(self, parser):
        parser.add_argument("--checkpoint", type=Path)
        parser.add_argument("--test-report", type=Path)

    def handle(self, *args, **options):
        project_root = Path(__file__).resolve().parents[4]
        checkpoint = options.get("checkpoint") or Path(
            os.environ.get(
                "NEORX_MODEL_PATH",
                project_root / "backend/models/neorx_effusion_categories_resnet50.pt",
            )
        )
        test_report = options.get("test_report") or (
            project_root / "qa/modelo_entrenado/classification_report.json"
        )
        checkpoint = checkpoint.resolve()
        test_report = test_report.resolve()
        if not checkpoint.is_file():
            raise CommandError(f"No existe el checkpoint: {checkpoint}")
        if not test_report.is_file():
            raise CommandError(f"No existe el reporte TEST: {test_report}")

        saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
        validation = saved.get("metrics", {})
        test = json.loads(test_report.read_text(encoding="utf-8"))
        labels = saved.get("pathologies", [])
        validation_auc = dict(zip(labels, validation.get("per_class_auc", [])))
        test_classes = test.get("per_class", {})
        epoch = int(saved.get("extra", {}).get("epoch", 0)) + 1
        expected = ["Effusion", "CategoryTumoral", "CategoryPleural", "CategoryInfectious", "CategoryInterstitial"]
        if labels != expected:
            raise CommandError(f"Clases inesperadas en el checkpoint: {labels}")

        self.stdout.write("NeoRX - evaluación del modelo entrenado")
        self.stdout.write(f"Checkpoint: {checkpoint.name}")
        self.stdout.write(f"Época seleccionada por VALIDACIÓN: {epoch}")
        self.stdout.write(f"Imágenes evaluadas en TEST: {test.get('test_samples'):,}")
        self.stdout.write("")
        self.stdout.write("Clase                         AUROC VAL     AUROC TEST")
        self.stdout.write("-------------------------------------------------------")
        for label in labels:
            val_auc = float(validation_auc[label]) * 100
            test_auc = float(test_classes[label]["auc"]) * 100
            self.stdout.write(f"{label:<29} {val_auc:>7.2f} %      {test_auc:>7.2f} %")

        validation_macro = float(validation["macro_auc"]) * 100
        test_macro = float(test["macro_auc"]) * 100
        effusion_test = float(test_classes["Effusion"]["auc"]) * 100
        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Fase de evaluación completada - macro AUROC TEST: {test_macro:.2f} %"
            )
        )
        self.stdout.write(
            f"Macro AUROC VALIDACIÓN: {validation_macro:.2f} % | "
            f"AUROC TEST derrame pleural: {effusion_test:.2f} %"
        )
        self.stdout.write(
            self.style.WARNING(
                "AUROC mide discriminación y no es accuracy. Los umbrales 0,99 del "
                "checkpoint no aprobaron sensibilidad clínica; las decisiones permanecen deshabilitadas."
            )
        )
