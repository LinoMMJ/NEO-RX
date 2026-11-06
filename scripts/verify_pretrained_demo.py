"""Verifica y materializa las cinco muestras de presentación de NeoRX.

No mide exactitud clínica. Es una comprobación reproducible de integración:
inferencia real, decisión de producto y Grad-CAM con el mismo modelo activo.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SOURCE = ROOT / "muestras_radiografias_demo"
OUTPUT = ROOT / "muestras_presentacion_preentrenado"

CASES = (
    ("01_derrame_pleural__00010834_000.png", "derrame_pleural", None),
    ("02_masa_pulmonar__00009671_004.png", "categoria_tumoral", "tumoral"),
    ("04_neumotorax__00027092_004.png", "categoria_pleural", "pleural"),
    ("10_infiltrado__00001381_003.png", "categoria_infecciosa", "infecciosa"),
    ("08_fibrosis__00004409_001.png", "categoria_intersticial", "intersticial"),
)


def _decode_data_url(value: str) -> bytes:
    return base64.b64decode(value.split(",", 1)[1])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=OUTPUT)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--backend", type=Path, default=BACKEND)
    args = parser.parse_args()

    os.environ["NEORX_MODEL_PATH"] = ""
    os.environ.setdefault("NEORX_MODEL_CACHE", str(args.backend / "models"))
    os.environ["NEORX_BASELINE_WEIGHTS"] = "resnet50-res512-all"
    os.environ["NEORX_DECISION_MODE"] = "pretrained_effusion_categories"
    os.environ["NEORX_BASELINE_MIN_SCORE"] = "0.50"
    os.environ["NEORX_CATEGORY_MARGIN"] = "0.00"
    os.environ.setdefault("NEORX_TORCH_THREADS", "4")

    sys.path.insert(0, str(args.backend))
    from diagnostico.gradcam import GeneradorGradCAM
    from diagnostico.services import DetectorTorax

    args.output.mkdir(parents=True, exist_ok=True)
    for generated in args.output.glob("*.png"):
        generated.unlink()
    model = DetectorTorax.cargar()
    rows = []

    for filename, expected_output, expected_category in CASES:
        source = args.source / filename
        if not source.is_file():
            raise FileNotFoundError(source)

        print(f"Verificando {filename}...", flush=True)
        started = time.perf_counter()
        result = DetectorTorax.desde_png(source)
        if expected_category is None:
            actual_output = (
                "derrame_pleural"
                if result["enfoque"]["estado"] == "hallazgos_prioritarios"
                else result["enfoque"]["estado"]
            )
            score = result["probabilidades"]["Effusion"]
        else:
            actual_output = f"categoria_{result['categoria'].get('clave')}"
            score = result["categoria"].get("puntuacion_modelo")

        if actual_output != expected_output:
            raise AssertionError(f"{filename}: esperado {expected_output}, obtenido {actual_output}")

        target = result["enfoque"]["objetivos_gradcam"][0]
        class_index = model.pathologies.index(target["etiqueta_en"])
        original = np.array(Image.open(source).convert("L"), dtype=np.float32)
        tensor = DetectorTorax._preprocesar(original, 255.0)
        cam = GeneradorGradCAM.calcular(model, tensor, class_index)
        if not np.isfinite(cam).all() or float(cam.max() - cam.min()) < 0.5:
            raise AssertionError(f"Grad-CAM vacío o inválido para {filename}")

        shutil.copy2(source, args.output / filename)
        overlay_name = f"mapa_calor__{Path(filename).stem}.png"
        heatmap_name = f"solo_calor__{Path(filename).stem}.png"
        (args.output / overlay_name).write_bytes(_decode_data_url(
            GeneradorGradCAM.overlay_base64(model, tensor, class_index, original, cam=cam)
        ))
        (args.output / heatmap_name).write_bytes(_decode_data_url(
            GeneradorGradCAM.overlay_solo_heatmap_base64(model, tensor, class_index, cam=cam)
        ))
        rows.append({
            "archivo": filename,
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "salida_esperada": expected_output,
            "salida_obtenida": actual_output,
            "puntuacion_tecnica": float(score),
            "objetivo_gradcam": target,
            "mapa_superpuesto": overlay_name,
            "mapa_solo_calor": heatmap_name,
            "segundos_inferencia_y_mapa": round(time.perf_counter() - started, 3),
        })
        print(f"  {actual_output}: {float(score):.4f}", flush=True)

    report = {
        "modelo": DetectorTorax._model_name,
        "resolucion": DetectorTorax._input_size,
        "modo": "demostracion_preentrenada_no_clinica",
        "casos_verificados": len(rows),
        "resultado": "5_de_5_salidas_de_presentacion_verificadas",
        "muestras": rows,
        "advertencia": (
            "Selección curada para demostrar integración y Grad-CAM. No es un conjunto "
            "independiente ni una medición de accuracy, sensibilidad o especificidad."
        ),
    }
    (args.output / "reporte_verificacion.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
