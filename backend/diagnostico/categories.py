"""Agrupación clínica conservadora de hallazgos radiográficos.

La CNN sigue estimando hallazgos individuales. Esta capa elige una sola
categoría para presentación únicamente cuando existe evidencia validada y una
separación suficiente respecto de la segunda categoría. En los demás casos se
abstiene para no transformar un empate técnico en una falsa certeza.
"""

from collections import OrderedDict


CATEGORY_DEFINITIONS = OrderedDict([
    ("tumoral", {
        "nombre": "Tumoral",
        "labels": ("Mass", "Nodule"),
    }),
    ("pleural", {
        "nombre": "Pleural",
        "labels": ("Effusion", "Pneumothorax", "Pleural_Thickening"),
    }),
    ("infecciosa", {
        "nombre": "Infecciosa",
        # Infiltration is nonspecific, but for this presentation taxonomy it
        # is grouped with infectious/inflammatory air-space patterns.
        "labels": ("Pneumonia", "Consolidation", "Infiltration"),
    }),
    ("intersticial", {
        "nombre": "Intersticial",
        "labels": ("Fibrosis", "Edema"),
    }),
])

CATEGORY_BY_LABEL = {
    label: key
    for key, definition in CATEGORY_DEFINITIONS.items()
    for label in definition["labels"]
}


def supported_category_labels(model_labels):
    """Return only labels covered by the four-category product scope."""
    available = set(model_labels or [])
    return [
        label
        for definition in CATEGORY_DEFINITIONS.values()
        for label in definition["labels"]
        if label in available
    ]


def select_primary_category(findings, minimum_margin=0.10):
    """Select one category from validated positive findings, or abstain.

    Evidence is the strongest normalized excess above the class threshold.
    This permits comparison without presenting the value as diagnostic
    probability. A close runner-up produces an explicit ambiguous result.
    """
    groups = []
    for key, definition in CATEGORY_DEFINITIONS.items():
        diseases = [item for item in findings if item.get("categoria") == key]
        detected = [item for item in diseases if item.get("detectado")]
        evidence = max((item.get("evidencia_categoria", 0.0) for item in detected), default=0.0)
        groups.append({
            "clave": key,
            "nombre": definition["nombre"],
            "evidencia": round(float(evidence), 6),
            "enfermedades": sorted(
                diseases,
                key=lambda item: item.get("probabilidad_estimada", 0.0),
                reverse=True,
            ),
            "detectadas": [item["etiqueta"] for item in detected],
        })

    ranked = sorted(groups, key=lambda item: item["evidencia"], reverse=True)
    eligible = [item for item in ranked if item["evidencia"] > 0]
    if not eligible:
        return {
            "estado": "no_concluyente",
            "clave": None,
            "nombre": "No concluyente",
            "mensaje": "Ninguna categoría alcanzó criterios de decisión validados.",
            "enfermedades": [],
            "categorias_evaluadas": groups,
        }

    winner = eligible[0]
    runner_up = eligible[1] if len(eligible) > 1 else None
    margin = winner["evidencia"] - (runner_up["evidencia"] if runner_up else 0.0)
    if runner_up and margin < minimum_margin:
        return {
            "estado": "ambigua",
            "clave": None,
            "nombre": "No concluyente",
            "mensaje": (
                f"Las categorías {winner['nombre'].lower()} y "
                f"{runner_up['nombre'].lower()} tienen evidencia demasiado cercana."
            ),
            "margen": round(margin, 6),
            "enfermedades": [],
            "categorias_evaluadas": groups,
        }

    return {
        "estado": "seleccionada",
        "clave": winner["clave"],
        "nombre": winner["nombre"],
        "mensaje": "Se muestra una sola categoría principal; requiere confirmación profesional.",
        "margen": round(margin, 6),
        "enfermedades": winner["enfermedades"],
        "categorias_evaluadas": groups,
    }
