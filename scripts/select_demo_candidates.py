"""Select transparent, labelled NIH demo candidates from saved validation predictions."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DISEASE_TO_HEAD = {
    "Effusion": "Effusion",
    "Mass": "CategoryTumoral",
    "Nodule": "CategoryTumoral",
    "Pneumothorax": "CategoryPleural",
    "Pleural_Thickening": "CategoryPleural",
    "Pneumonia": "CategoryInfectious",
    "Consolidation": "CategoryInfectious",
    "Fibrosis": "CategoryInterstitial",
    "Edema": "CategoryInterstitial",
    "Infiltration": "CategoryInterstitial",
}


def main():
    saved = np.load(ROOT / "qa/modelo_entrenado/validation_predictions.npz")
    labels = list(saved["labels"])
    probabilities = saved["probabilities"]
    image_ids = saved["image_ids"].astype(str)
    with zipfile.ZipFile(ROOT / "results.zip") as archive:
        frame = pd.read_csv(
            io.BytesIO(archive.read("manifests-focused5/clean_manifest.csv"))
        ).set_index("Image Index")

    selected = []
    for disease, head in DISEASE_TO_HEAD.items():
        column = labels.index(head)
        candidates = []
        for index, image_id in enumerate(image_ids):
            raw = str(frame.at[image_id, "Finding Labels"])
            findings = raw.split("|")
            if disease in findings:
                scores = {label: float(probabilities[index, labels.index(label)]) for label in labels}
                categories = [
                    scores["CategoryTumoral"], scores["CategoryPleural"],
                    scores["CategoryInfectious"], scores["CategoryInterstitial"],
                ]
                expected = scores[head]
                sorted_categories = sorted(categories, reverse=True)
                route_matches = (
                    expected >= 0.50
                    if disease == "Effusion"
                    else (
                        scores["Effusion"] < 0.50
                        and expected == sorted_categories[0]
                        and expected - sorted_categories[1] >= 0.08
                    )
                )
                candidates.append(
                    {
                        "disease": disease,
                        "expected_head": head,
                        "image_id": image_id,
                        "source_labels": findings,
                        "saved_validation_score": float(probabilities[index, column]),
                        "single_label": len(findings) == 1,
                        "route_matches_demo": route_matches,
                        "saved_scores": scores,
                    }
                )
        routed = [item for item in candidates if item["route_matches_demo"]]
        if not routed:
            raise RuntimeError(f"No demo-compatible validation sample found for {disease}")
        # Prefer an isolated source label among samples that satisfy the exact
        # deployed demo routing, then the strongest frozen validation score.
        isolated = [item for item in routed if item["single_label"]]
        pool = isolated or routed
        selected.append(max(pool, key=lambda item: item["saved_validation_score"]))

    output = ROOT / "backend/models/muestras_radiografias" / "seleccion.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(selected, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(selected, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
