"""Temporary presentation policy for a TorchXRayVision pretrained model.

The model still emits independent radiographic scores.  This module limits
what the product presents: Effusion is the only specific finding; otherwise it
offers at most one broad category.  It does not turn scores into diagnoses.
"""

import math

from .categories import CATEGORY_DEFINITIONS


STRATEGY = "pretrained_effusion_categories_v1"
PRIMARY_LABEL = "Effusion"


def _score(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) and 0 <= value <= 1 else None


def pretrained_result(scores, names, minimum_score=0.50, category_margin=0.10):
    """Apply a conservative display policy to normalized pretrained outputs."""
    minimum_score = float(minimum_score)
    category_margin = float(category_margin)
    if not 0.40 <= minimum_score <= 0.95:
        raise ValueError("minimum_score must be between 0.40 and 0.95")
    if not math.isfinite(category_margin) or not 0 <= category_margin <= 0.50:
        raise ValueError("category_margin must be between 0 and 0.50")

    clean = {label: value for label, raw in (scores or {}).items()
             if (value := _score(raw)) is not None}
    primary_score = clean.get(PRIMARY_LABEL)
    primary_detected = primary_score is not None and primary_score >= minimum_score
    primary_row = None
    if primary_score is not None:
        primary_row = {
            "etiqueta_en": PRIMARY_LABEL,
            "etiqueta": names.get(PRIMARY_LABEL, "Derrame pleural"),
            "probabilidad_estimada": primary_score,
            "threshold_usado": minimum_score,
            "decision_habilitada": True,
            "detectado": primary_detected,
            "tipo_salida": "prioritaria",
            "estado_validacion": "punto_operativo_preentrenado",
        }

    category = {
        "estado": "no_concluyente", "clave": None,
        "nombre": "No concluyente", "enfermedades": [],
    }
    detected = [primary_row] if primary_detected else []
    targets = []

    if primary_detected:
        state = "hallazgos_prioritarios"
        title = "Señal prioritaria: derrame pleural"
        message = (
            "El modelo preentrenado superó su punto operativo para derrame pleural. "
            "La puntuación requiere confirmación profesional y no equivale a certeza diagnóstica."
        )
        targets = [{"etiqueta_en": PRIMARY_LABEL, "etiqueta": names.get(PRIMARY_LABEL, "Derrame pleural")}]
    else:
        ranked = []
        for key, definition in CATEGORY_DEFINITIONS.items():
            # Effusion is exclusively handled by the priority branch.  Outputs
            # without a defensible mapping (for example Atelectasis) are not
            # forced into one of the four requested categories.
            candidates = [
                (clean[label], label)
                for label in definition["labels"]
                if label != PRIMARY_LABEL and label in clean
            ]
            if candidates:
                score, contributor = max(candidates)
                ranked.append((score, key, definition["nombre"], contributor))
        ranked.sort(reverse=True)
        eligible = [row for row in ranked if row[0] >= minimum_score]
        separation = eligible[0][0] - eligible[1][0] if len(eligible) > 1 else None

        if eligible and (separation is None or separation >= category_margin):
            score, key, name, contributor = eligible[0]
            state = "orientacion_categoria"
            title = f"Orientación por categoría: {name}"
            message = (
                "No se mostró derrame pleural. La señal restante se resume únicamente "
                "como categoría y requiere revisión profesional."
            )
            category.update(
                estado="seleccionada", clave=key, nombre=name, mensaje=message,
                puntuacion_modelo=score,
            )
            targets = [{"etiqueta_en": contributor, "etiqueta": f"Orientación {name.lower()}"}]
        elif len(eligible) > 1:
            state = "no_concluyente"
            title = "Categoría no concluyente"
            message = "Dos categorías tienen puntuaciones cercanas; el sistema no fuerza una selección."
        else:
            state = "no_concluyente"
            title = "Sin señal suficiente"
            message = (
                "Ninguna salida presentada alcanzó el punto operativo. "
                "Esto no confirma normalidad ni descarta enfermedad."
            )

    category.setdefault("mensaje", message)
    findings = [primary_row] if primary_row else []
    return {
        "enfoque": {
            "version": STRATEGY,
            "estado": state,
            "prioritarias": [PRIMARY_LABEL],
            "hallazgos_detectados": detected,
            "checkpoint_compatible": True,
            "objetivos_gradcam": targets,
            "umbral_operativo": minimum_score,
            "modo": "preentrenado",
        },
        "decision": {
            "estado": state,
            "titulo": title,
            "mensaje": message,
            "hallazgos_principales": [row["etiqueta"] for row in detected],
        },
        "categoria": category,
        "hallazgos": findings,
        "alcance": ["Derrame pleural", "Categoría tumoral", "Categoría pleural", "Categoría infecciosa", "Categoría intersticial"],
        "probabilidades": clean,
        "thresholds": {label: minimum_score for label in clean},
    }
