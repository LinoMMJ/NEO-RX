"""
Niveles clínicos centralizados — Single Source of Truth para umbrales.

Este módulo define TODOS los umbrales clínicos en UN solo lugar (backend),
eliminando los 5+ duplicados que existían en el frontend.

La API expone estos niveles para que el frontend los consuma dinámicamente.
"""

from dataclasses import dataclass
from typing import Dict, Literal

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN CENTRAL DE UMBRALES
# ──────────────────────────────────────────────────────────────────────────────

# Niveles clínicos estándar (basados en guías radiológicas y calibración modelo)
NIVEL_ALTO = 0.65      # >65%: Hallazgo positivo, requiere correlación clínica urgente
NIVEL_MODERADO = 0.40  # 40-65%: Hallazgo moderado, correlación clínica recomendada
NIVEL_LEVE = 0.20      # 20-40%: Hallazgo leve/marginal, considerar seguimiento
# <20%: Marginal/insignificante

# Umbrales específicos por patología (sobrescriben los generales si existen)
# Formato: {patologia: {"alto": float, "moderado": float, "leve": float}}
UMBRALES_PATOLOGIA: Dict[str, Dict[str, float]] = {
    # Infecciones e inflamación - más conservadores (alta especificidad requerida)
    "Neumonía":          {"alto": 0.60, "moderado": 0.35, "leve": 0.15},
    "Consolidación":     {"alto": 0.60, "moderado": 0.35, "leve": 0.15},
    "Infiltrado":        {"alto": 0.55, "moderado": 0.30, "leve": 0.15},
    # Opacidades
    "Opacidad pulmonar": {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    "Lesión pulmonar":   {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    # Patología pleural - derrame/neumotórax son críticos
    "Derrame pleural":   {"alto": 0.65, "moderado": 0.40, "leve": 0.20},
    "Neumotórax":        {"alto": 0.70, "moderado": 0.45, "leve": 0.20},
    "Engrosamiento pleural": {"alto": 0.55, "moderado": 0.35, "leve": 0.20},
    # Obstructiva/intersticial
    "Atelectasia":       {"alto": 0.55, "moderado": 0.35, "leve": 0.15},
    "Enfisema":          {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    "Fibrosis pulmonar": {"alto": 0.55, "moderado": 0.35, "leve": 0.15},
    "Edema pulmonar":    {"alto": 0.60, "moderado": 0.35, "leve": 0.15},
    # Lesiones focales
    "Nódulo pulmonar":   {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    "Masa pulmonar":     {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
}

# Nombres de niveles para frontend
NIVEL_LABELS = {
    "alto": "Alto",
    "moderado": "Moderado",
    "leve": "Leve",
    "marginal": "No significativo",
}

NIVEL_COLORS = {
    "alto": "danger",
    "moderado": "orange",
    "leve": "warning",
    "marginal": "slate",
}

# ──────────────────────────────────────────────────────────────────────────────
# DATACLASS PARA TIPO SEGURO
# ──────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NivelClinico:
    """Resultado de clasificación de una probabilidad."""
    etiqueta: Literal["alto", "moderado", "leve", "marginal"]
    color: str
    umbral_usado: float
    descripcion: str

# ──────────────────────────────────────────────────────────────────────────────
# FUNCIONES PÚBLICAS
# ──────────────────────────────────────────────────────────────────────────────

def obtener_umbrales(patologia: str) -> Dict[str, float]:
    """
    Retorna umbrales específicos para una patología.
    Si no existe, usa los generales (NIVEL_ALTO, NIVEL_MODERADO, NIVEL_LEVE).
    """
    return UMBRALES_PATOLOGIA.get(patologia, {
        "alto": NIVEL_ALTO,
        "moderado": NIVEL_MODERADO,
        "leve": NIVEL_LEVE,
    })


def clasificar_probabilidad(patologia: str, probabilidad: float) -> NivelClinico:
    """
    Clasifica una probabilidad en nivel clínico según umbrales de la patología.
    """
    u = obtener_umbrales(patologia)
    if probabilidad >= u["alto"]:
        return NivelClinico(
            etiqueta="alto",
            color=NIVEL_COLORS["alto"],
            umbral_usado=u["alto"],
            descripcion=f"Probabilidad ≥ {int(u['alto']*100)}%: Hallazgo positivo, correlación clínica urgente",
        )
    if probabilidad >= u["moderado"]:
        return NivelClinico(
            etiqueta="moderado",
            color=NIVEL_COLORS["moderado"],
            umbral_usado=u["moderado"],
            descripcion=f"Probabilidad {int(u['moderado']*100)}–{int(u['alto']*100)}%: Hallazgo moderado, correlación clínica recomendada",
        )
    if probabilidad >= u["leve"]:
        return NivelClinico(
            etiqueta="leve",
            color=NIVEL_COLORS["leve"],
            umbral_usado=u["leve"],
            descripcion=f"Probabilidad {int(u['leve']*100)}–{int(u['moderado']*100)}%: Hallazgo leve, considerar seguimiento",
        )
    return NivelClinico(
        etiqueta="marginal",
        color=NIVEL_COLORS["marginal"],
        umbral_usado=u["leve"],
        descripcion=f"Probabilidad < {int(u['leve']*100)}%: No significativo",
    )


def clasificar_todas(patologias: Dict[str, float]) -> Dict[str, Dict]:
    """
    Clasifica un diccionario completo de patologías → probabilidades.
    Retorna dict con {patologia: {nivel, color, umbral, descripcion, probabilidad}}.
    """
    resultado = {}
    for nombre, prob in patologias.items():
        nivel = clasificar_probabilidad(nombre, prob)
        resultado[nombre] = {
            "probabilidad": prob,
            "nivel": nivel.etiqueta,
            "color": nivel.color,
            "umbral": nivel.umbral_usado,
            "descripcion": nivel.descripcion,
            "etiqueta": NIVEL_LABELS[nivel.etiqueta],
        }
    return resultado


def get_api_response() -> Dict:
    """
    Retorna toda la configuración para la API /api/niveles-clinicos/
    """
    return {
        "niveles_generales": {
            "alto": NIVEL_ALTO,
            "moderado": NIVEL_MODERADO,
            "leve": NIVEL_LEVE,
        },
        "umbrales_por_patologia": {
            k: {"alto": v["alto"], "moderado": v["moderado"], "leve": v["leve"]}
            for k, v in UMBRALES_PATOLOGIA.items()
        },
        "labels": NIVEL_LABELS,
        "colors": NIVEL_COLORS,
        "version": "1.0",
    }