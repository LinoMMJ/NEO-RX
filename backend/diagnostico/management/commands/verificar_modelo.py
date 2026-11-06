"""Verify the locally cached pretrained model without changing clinical data."""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path

import numpy as np
from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps

from diagnostico.services import DetectorTorax


class Command(BaseCommand):
    help = (
        "Carga el modelo CNN configurado, ejecuta inferencias técnicas repetibles "
        "y guarda un reporte JSON. No calcula exactitud clínica."
    )

    def add_arguments(self, parser):
        parser.add_argument("--runs", type=int, default=5, help="Número de inferencias (1-50).")
        parser.add_argument("--image", type=Path, help="Radiografía opcional para la prueba técnica.")
        parser.add_argument("--output", type=Path, help="Ruta opcional para guardar el reporte JSON.")

    def handle(self, *args, **options):
        runs = options["runs"]
        if not 1 <= runs <= 50:
            raise CommandError("--runs debe estar entre 1 y 50")

        array, maxval, input_info = self._input(options.get("image"))
        started = time.perf_counter()
        model = DetectorTorax.cargar()
        load_seconds = time.perf_counter() - started

        rows = []
        reference = None
        maximum_repeat_difference = 0.0
        for index in range(1, runs + 1):
            tick = time.perf_counter()
            result = DetectorTorax.predecir(array, maxval)
            elapsed = time.perf_counter() - tick
            scores = np.asarray(
                [result["probabilidades"][label] for label in model.pathologies],
                dtype=np.float64,
            )
            valid = (
                scores.size == len(model.pathologies)
                and np.isfinite(scores).all()
                and ((0.0 <= scores) & (scores <= 1.0)).all()
            )
            if reference is None:
                reference = scores
            else:
                maximum_repeat_difference = max(
                    maximum_repeat_difference,
                    float(np.max(np.abs(reference - scores))),
                )
            rows.append({"run": index, "seconds": round(elapsed, 4), "valid": bool(valid)})
            status = self.style.SUCCESS("OK") if valid else self.style.ERROR("ERROR")
            self.stdout.write(f"[{index}/{runs}] Inferencia {status} - {elapsed:.3f} s")

        successful = sum(row["valid"] for row in rows)
        latencies = [row["seconds"] for row in rows]
        weights = self._weights_file()
        report = {
            "status": "passed" if successful == runs else "failed",
            "model": result["modelo"],
            "architecture": type(model).__name__,
            "input_resolution": result["resolucion_entrada"],
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "pathology_outputs": len(model.pathologies),
            "weights": {
                "path": str(weights) if weights else None,
                "bytes": weights.stat().st_size if weights else None,
                "sha256": self._sha256(weights) if weights else None,
            },
            "input": input_info,
            "load_and_warmup_seconds": round(load_seconds, 4),
            "runs": rows,
            "successful_runs": successful,
            "technical_execution_rate": successful / runs,
            "latency_seconds": {
                "minimum": min(latencies),
                "mean": round(sum(latencies) / len(latencies), 4),
                "maximum": max(latencies),
            },
            "maximum_repeat_difference": maximum_repeat_difference,
            "clinical_metrics": None,
            "notice": (
                "Esta es una prueba técnica de integración y rendimiento. "
                "No representa accuracy, sensibilidad, especificidad ni eficacia clínica."
            ),
        }

        if options.get("output"):
            output = options["output"].resolve()
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
            self.stdout.write(f"Reporte: {output}")

        if successful != runs or not math.isclose(maximum_repeat_difference, 0.0, abs_tol=1e-6):
            raise CommandError("La verificación técnica del modelo no fue consistente")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Fase de integración completada - {successful}/{runs} "
                "inferencias válidas (100% de ejecución técnica)"
            )
        )
        self.stdout.write(
            f"Modelo: {report['model']} | entrada: {report['input_resolution']} px | "
            f"parámetros: {report['parameters']:,}"
        )
        self.stdout.write(
            f"Latencia media: {report['latency_seconds']['mean']:.3f} s | "
            f"carga y precalentamiento: {load_seconds:.3f} s"
        )
        self.stdout.write(self.style.WARNING(report["notice"]))

    @staticmethod
    def _input(path):
        if path:
            path = path.resolve()
            if not path.is_file():
                raise CommandError(f"No existe la imagen: {path}")
            if path.suffix.lower() in {".dcm", ".dicom"}:
                from estudios.utils import dicom_display_pixels, leer_dicom

                array = dicom_display_pixels(leer_dicom(path)).astype(np.float32)
            else:
                with Image.open(path) as source:
                    array = np.asarray(
                        ImageOps.exif_transpose(source).convert("L"), dtype=np.float32
                    )
            return array, 255.0, {
                "kind": "radiograph_without_ground_truth",
                "filename": path.name,
                "sha256": Command._sha256(path),
            }

        # Deterministic, non-clinical phantom: exercises preprocessing and CNN
        # execution without presenting its scores as a patient result.
        axis = np.linspace(-1.0, 1.0, 768, dtype=np.float32)
        yy, xx = np.meshgrid(axis, axis, indexing="ij")
        phantom = np.clip(220.0 - 150.0 * np.sqrt(xx * xx + yy * yy) + 20.0 * yy, 0, 255)
        return phantom.astype(np.float32), 255.0, {"kind": "non_clinical_phantom"}

    @staticmethod
    def _weights_file():
        configured = os.environ.get("NEORX_MODEL_PATH")
        if configured and Path(configured).is_file():
            return Path(configured).resolve()
        cache = Path(
            os.environ.get(
                "NEORX_MODEL_CACHE",
                Path(__file__).resolve().parents[3] / "models",
            )
        )
        model_name = os.environ.get("NEORX_BASELINE_WEIGHTS", "densenet121-res224-all")
        token = "densenet121" if model_name.startswith("densenet") else "resnet50"
        candidates = sorted(cache.glob(f"*{token}*.pt"), key=lambda item: item.stat().st_mtime, reverse=True)
        return candidates[0].resolve() if candidates else None

    @staticmethod
    def _sha256(path):
        digest = hashlib.sha256()
        with Path(path).open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()
