"""Busca cinco muestras NIH nuevas y verifica la salida real de NeoRX.

La selección es deliberadamente curada para una demostración técnica. No es un
conjunto independiente ni estima exactitud, sensibilidad o especificidad.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
DEFAULT_CACHE = ROOT / "tmp" / "demo_candidate_search"
DEFAULT_OUTPUT = ROOT / "tmp" / "muestras_presentacion_20261109"
S3_TEMPLATE = "https://nih-chest-x-rays.s3.us-east-2.amazonaws.com/images_1024x1024/{image_id}"

ROUTES = {
    "derrame_pleural": {
        "order": 1,
        "title": "Derrame pleural",
        "labels": ("Effusion",),
        "category": None,
    },
    "categoria_tumoral": {
        "order": 2,
        "title": "Categoría tumoral",
        "labels": ("Mass", "Nodule"),
        "category": "tumoral",
    },
    "categoria_pleural": {
        "order": 3,
        "title": "Categoría pleural",
        "labels": ("Pneumothorax", "Pleural_Thickening"),
        "category": "pleural",
    },
    "categoria_infecciosa": {
        "order": 4,
        "title": "Categoría infecciosa",
        "labels": ("Pneumonia", "Consolidation", "Infiltration"),
        "category": "infecciosa",
    },
    "categoria_intersticial": {
        "order": 5,
        "title": "Categoría intersticial",
        "labels": ("Fibrosis", "Edema"),
        "category": "intersticial",
    },
}


def _decode_data_url(value: str) -> bytes:
    return base64.b64decode(value.split(",", 1)[1])


def _existing_ids() -> set[str]:
    ids: set[str] = set()
    pattern = re.compile(r"\d{8}_\d{3}\.png$")
    for folder in (ROOT / "muestras_radiografias_demo", ROOT / "muestras_presentacion_preentrenado"):
        if not folder.exists():
            continue
        for path in folder.rglob("*.png"):
            match = pattern.search(path.name)
            if match:
                ids.add(match.group(0))
    return ids


def _manifest() -> pd.DataFrame:
    with zipfile.ZipFile(ROOT / "results.zip") as archive:
        raw = archive.read("manifests-focused5/clean_manifest.csv")
    return pd.read_csv(io.BytesIO(raw))


def _candidate_rows(frame: pd.DataFrame, per_label: int) -> list[dict]:
    excluded = _existing_ids()
    rows: list[dict] = []
    for route, spec in ROUTES.items():
        for label in spec["labels"]:
            pool = frame[
                (frame["Finding Labels"] == label)
                & (~frame["Image Index"].isin(excluded))
                & (frame["pixel_std"].between(45.0, 85.0))
            ].copy()
            # Prefer frontal PA studies, then sample deterministically to avoid
            # merely taking adjacent studies from the same patient.
            pool["pa_first"] = (pool["View Position"] == "PA").astype(int)
            seed = int(hashlib.sha256(label.encode()).hexdigest()[:8], 16)
            pa = pool[pool["pa_first"] == 1]
            source = pa if len(pa) >= per_label else pool
            picked = source.sample(n=min(per_label, len(source)), random_state=seed)
            for item in picked.to_dict("records"):
                rows.append({
                    "route": route,
                    "source_label": label,
                    "image_id": item["Image Index"],
                    "patient_id": int(item["Patient ID"]),
                    "view": item["View Position"],
                    "pixel_std": float(item["pixel_std"]),
                    "expected_sha256": item["sha256"],
                })
    return rows


def _download(rows: list[dict], cache: Path) -> list[dict]:
    cache.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for index, row in enumerate(rows, 1):
        target = cache / row["image_id"]
        if not target.is_file():
            request = urllib.request.Request(
                S3_TEMPLATE.format(image_id=row["image_id"]),
                headers={"User-Agent": "NeoRX-demo-verification/1.0"},
            )
            try:
                with urllib.request.urlopen(request, timeout=45) as response:
                    target.write_bytes(response.read())
            except Exception as exc:
                print(f"DESCARGA FALLIDA {row['image_id']}: {exc}", flush=True)
                continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if row["expected_sha256"] and digest != row["expected_sha256"]:
            print(f"HASH DISTINTO {row['image_id']}; se descarta", flush=True)
            target.unlink(missing_ok=True)
            continue
        downloaded.append({**row, "path": target})
        print(f"Descarga {index}/{len(rows)}: {row['image_id']}", flush=True)
    return downloaded


def _route_and_score(result: dict, expected_route: str) -> tuple[bool, float]:
    if expected_route == "derrame_pleural":
        valid = result.get("enfoque", {}).get("estado") == "hallazgos_prioritarios"
        return valid, float(result.get("probabilidades", {}).get("Effusion", 0.0))
    expected = ROUTES[expected_route]["category"]
    category = result.get("categoria", {})
    valid = category.get("estado") == "seleccionada" and category.get("clave") == expected
    return valid, float(category.get("puntuacion_modelo") or 0.0)


def _screen(rows: list[dict], batch_size: int) -> list[dict]:
    sys.path.insert(0, str(BACKEND))
    from diagnostico.pretrained_policy import pretrained_result
    from diagnostico.services import DetectorTorax, PATOLOGIAS_NEUMOLOGIA_BASELINE

    model = DetectorTorax.cargar()
    selected: dict[str, dict] = {}
    for start in range(0, len(rows), batch_size):
        group = rows[start:start + batch_size]
        tensors = []
        valid_rows = []
        for row in group:
            try:
                with Image.open(row["path"]) as source:
                    array = np.asarray(source.convert("L"), dtype=np.float32)
                tensors.append(DetectorTorax._preprocesar(array, 255.0))
                valid_rows.append({**row, "array": array})
            except Exception as exc:
                print(f"LECTURA FALLIDA {row['image_id']}: {exc}", flush=True)
        if not tensors:
            continue
        batch = torch.cat(tensors).contiguous(memory_format=torch.channels_last)
        with torch.inference_mode():
            outputs = model(batch).cpu().numpy()
        for row, values in zip(valid_rows, outputs):
            scores = {label: float(value) for label, value in zip(model.pathologies, values)}
            result = pretrained_result(
                scores,
                PATOLOGIAS_NEUMOLOGIA_BASELINE,
                minimum_score=0.50,
                category_margin=0.00,
            )
            matches, score = _route_and_score(result, row["route"])
            print(
                f"{row['image_id']} [{row['source_label']}] -> "
                f"{result['decision']['titulo']} ({score:.4f})",
                flush=True,
            )
            if matches and (row["route"] not in selected or score > selected[row["route"]]["score"]):
                selected[row["route"]] = {**row, "result": result, "score": score}

    missing = [route for route in ROUTES if route not in selected]
    if missing:
        raise RuntimeError("No se encontraron candidatos válidos para: " + ", ".join(missing))
    return [selected[route] for route in ROUTES]


def _materialize(selected: list[dict], output: Path) -> None:
    from diagnostico.gradcam import GeneradorGradCAM
    from diagnostico.services import DetectorTorax

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    model = DetectorTorax.cargar()
    report_rows = []
    for row in selected:
        spec = ROUTES[row["route"]]
        target_info = row["result"]["enfoque"]["objetivos_gradcam"][0]
        class_index = list(model.pathologies).index(target_info["etiqueta_en"])
        tensor = DetectorTorax._preprocesar(row["array"], 255.0)
        cam = GeneradorGradCAM.calcular(model, tensor, class_index)
        visual = GeneradorGradCAM._preparar_mapa_visual(cam)
        coverage = float(np.mean(visual >= 0.20))
        if not np.isfinite(cam).all() or float(cam.max() - cam.min()) < 0.5 or coverage < 0.002:
            raise RuntimeError(f"Grad-CAM inválido o demasiado vacío para {row['image_id']}")

        filename = f"{spec['order']:02d}_{row['route']}__{row['image_id']}"
        shutil.copy2(row["path"], output / filename)
        overlay_name = f"mapa_calor__{Path(filename).stem}.png"
        heatmap_name = f"solo_calor__{Path(filename).stem}.png"
        (output / overlay_name).write_bytes(_decode_data_url(
            GeneradorGradCAM.overlay_base64(model, tensor, class_index, row["array"], cam=cam)
        ))
        (output / heatmap_name).write_bytes(_decode_data_url(
            GeneradorGradCAM.overlay_solo_heatmap_base64(model, tensor, class_index, cam=cam)
        ))
        report_rows.append({
            "salida": row["route"],
            "titulo": spec["title"],
            "archivo": filename,
            "image_id_nih": row["image_id"],
            "etiqueta_fuente_nih": row["source_label"],
            "vista": row["view"],
            "puntuacion_tecnica": row["score"],
            "decision_obtenida": row["result"]["decision"],
            "objetivo_gradcam": target_info,
            "cobertura_visual_ge_0_20": coverage,
            "mapa_superpuesto": overlay_name,
            "mapa_solo_calor": heatmap_name,
            "sha256": hashlib.sha256(row["path"].read_bytes()).hexdigest(),
        })

    report = {
        "modelo": DetectorTorax._model_name,
        "resolucion": DetectorTorax._input_size,
        "fecha_seleccion": "2026-11-10",
        "resultado": "5_de_5_rutas_y_mapas_verificados",
        "muestras": report_rows,
        "advertencia": (
            "Selección curada para demostrar integración y Grad-CAM. No es un conjunto "
            "independiente ni mide precisión clínica. Las etiquetas NIH fueron extraídas "
            "automáticamente de informes y pueden contener ruido."
        ),
        "fuente": "NIH Clinical Center ChestX-ray14",
        "fuente_url": "https://nihcc.app.box.com/v/ChestXray-NIHCC",
    }
    (output / "reporte_verificacion.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Cinco muestras nuevas verificadas en NeoRX",
        "",
        "Estas imágenes fueron seleccionadas de NIH ChestX-ray14 y pasadas por el",
        "mismo ResNet-50 y Grad-CAM regional que utiliza el sistema.",
        "",
        "| Salida demostrativa | Archivo | Puntuación técnica |",
        "| --- | --- | ---: |",
    ]
    for item in report_rows:
        lines.append(f"| {item['titulo']} | `{item['archivo']}` | {item['puntuacion_tecnica'] * 100:.2f}/100 |")
    lines.extend([
        "",
        "Cada original tiene `mapa_calor__*.png` y `solo_calor__*.png`.",
        "La puntuación es una activación técnica, no certeza diagnóstica.",
        "La selección es curada para demostración y no constituye una evaluación independiente.",
        "",
        "Fuente oficial: https://nihcc.app.box.com/v/ChestXray-NIHCC",
    ])
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-label", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    os.environ["NEORX_MODEL_PATH"] = ""
    os.environ["NEORX_MODEL_CACHE"] = str(BACKEND / "models")
    os.environ["NEORX_BASELINE_WEIGHTS"] = "resnet50-res512-all"
    os.environ["NEORX_DECISION_MODE"] = "pretrained_effusion_categories"
    os.environ["NEORX_BASELINE_MIN_SCORE"] = "0.50"
    os.environ["NEORX_CATEGORY_MARGIN"] = "0.00"
    os.environ.setdefault("NEORX_TORCH_THREADS", "4")

    rows = _candidate_rows(_manifest(), args.per_label)
    downloaded = _download(rows, args.cache)
    selected = _screen(downloaded, args.batch_size)
    _materialize(selected, args.output)
    print(json.dumps({
        "output": str(args.output),
        "selected": [item["image_id"] for item in selected],
    }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
