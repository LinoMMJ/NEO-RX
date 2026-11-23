"""Compare the previous 0.99 cutoff with the deployed validation thresholds.

This is an integration demonstration over curated images, not an accuracy or
clinical-validity estimate. Model weights and raw scores are identical in both
columns; only the binary operating point changes.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "neorx.settings")
sys.path.insert(0, "/app")

import django  # noqa: E402

django.setup()

from diagnostico.services import DetectorTorax  # noqa: E402


OLD_THRESHOLD = 0.99
ROOT = Path(__file__).resolve().parent


def main() -> int:
    DetectorTorax.cargar()
    thresholds = dict(DetectorTorax._thresholds)
    rows = []
    for image in sorted(ROOT.glob("*.png")):
        started = time.perf_counter()
        result = DetectorTorax.desde_png(image)
        scores = {key: float(value) for key, value in result["probabilidades"].items()}
        old_positive = sorted(label for label, score in scores.items() if score >= OLD_THRESHOLD)
        new_positive = sorted(
            label for label, score in scores.items() if score >= thresholds[label]
        )
        row = {
            "archivo": image.name,
            "puntuaciones": {key: round(value, 6) for key, value in scores.items()},
            "positivas_con_099": old_positive,
            "positivas_con_nuevos_umbrales": new_positive,
            "decision_actual": result["decision"]["estado"],
            "titulo_actual": result["decision"]["titulo"],
            "categoria_actual": result.get("categoria", {}).get("clave"),
            "segundos": round(time.perf_counter() - started, 3),
        }
        rows.append(row)
        print(
            f"{image.name}: 0.99={old_positive or ['ninguna']} | "
            f"nuevos={new_positive or ['ninguna']} | {row['titulo_actual']}",
            flush=True,
        )

    summary = {
        "modelo": DetectorTorax._model_name,
        "imagenes": len(rows),
        "umbrales_anteriores": {label: OLD_THRESHOLD for label in thresholds},
        "umbrales_actuales": thresholds,
        "imagenes_con_alguna_senal_antes": sum(bool(row["positivas_con_099"]) for row in rows),
        "imagenes_con_alguna_senal_ahora": sum(
            bool(row["positivas_con_nuevos_umbrales"]) for row in rows
        ),
        "advertencia": (
            "Muestras curadas de integración; no estiman sensibilidad, especificidad ni precisión."
        ),
        "casos": rows,
    }
    print("RESULT_JSON=" + json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
