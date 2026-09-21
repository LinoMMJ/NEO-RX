"""
Niveles clínicos centralizados — Single Source of Truth para umbrales de VISUALIZACIÓN.

IMPORTANTE - DISTINCIÓN CRÍTICA:

1. THRESHOLDS DEL MODELO (detección):
   - Provienen del CHECKPOINT (optimizados en VALIDATION via Youden's J)
   - Determinan si un hallazgo se considera "detectado" (sí/no)
   - Son umbrales binarios por clase
   - NO se definen aquí, se cargan del modelo

2. NIVELES CLÍNICOS (visualización en frontend):
   - Son para CODIFICACIÓN DE COLOR / UI únicamente
   - Transforman una probabilidad continua en categorías visuales (Alto/Moderado/Leve/Marginal)
   - NO son thresholds de decisión del modelo
   - Pueden ser configurables por patología para mejor UX

Estos dos conceptos son INDEPENDIENTES:
- Un hallazgo puede estar "detectado" (prob > threshold_modelo) pero ser "Leve" en UI
- Un hallazgo puede NO estar "detectado" pero tener nivel "Leve" en UI si prob > 0.20

IMPORTANTE: Todos los valores son PENDIENTE DE EJECUCIÓN EXPERIMENTAL / CONFIGURACIÓN CLÍNICA.
"""

from dataclasses import dataclass
from typing import Dict, Literal, Optional

# ──────────────────────────────────────────────────────────────────────────────
# CONFIGURACIÓN DE NIVELES DE VISUALIZACIÓN (UI/UX)
# ──────────────────────────────────────────────────────────────────────────────

# Niveles generales por defecto (para patologías sin configuración específica)
# Estos son umbrales de VISUALIZACIÓN, no de decisión del modelo.
NIVEL_ALTO_VISUAL = 0.65      # ≥65%: Rojo/Alto - atención prioritaria
NIVEL_MODERADO_VISUAL = 0.40  # 40-65%: Naranja/Moderado - revisar
NIVEL_LEVE_VISUAL = 0.20      # 20-40%: Amarillo/Leve - seguimiento
# <20%: Gris/Marginal - no significativo visualmente

# Umbrales de visualización específicos por patología (en español, como llegan del frontend)
# Sobrescriben los generales si existen.
# FORMATO: {patologia_es: {"alto": float, "moderado": float, "leve": float}}
UMBRALES_VISUALES_PATOLOGIA: Dict[str, Dict[str, float]] = {
    # Infecciones e inflamación - más conservadores visualmente
    "Neumonía":          {"alto": 0.60, "moderado": 0.35, "leve": 0.15},
    "Consolidación":     {"alto": 0.60, "moderado": 0.35, "leve": 0.15},
    "Infiltrado pulmonar": {"alto": 0.55, "moderado": 0.30, "leve": 0.15},
    # Opacidades
    "Opacidad pulmonar": {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    "Lesión pulmonar":   {"alto": 0.50, "moderado": 0.30, "leve": 0.15},
    # Patología pleural
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
class NivelVisual:
    """Resultado de clasificación visual de una probabilidad (para UI)."""
    etiqueta: Literal["alto", "moderado", "leve", "marginal"]
    color: str
    umbral_visual_usado: float
    descripcion: str
    probabilidad: float
    detectado_por_modelo: Optional[bool] = None
    threshold_modelo: Optional[float] = None


# ──────────────────────────────────────────────────────────────────────────────
# FUNCIONES PÚBLICAS
# ──────────────────────────────────────────────────────────────────────────────

def obtener_umbrales_visuales(patologia_es: str) -> Dict[str, float]:
    """
    Retorna umbrales de VISUALIZACIÓN para una patología (en español).
    Si no existe configuración específica, usa los generales.

    NOTA: Estos son para CODIFICACIÓN DE COLOR en frontend, NO para decisión del modelo.
    """
    return UMBRALES_VISUALES_PATOLOGIA.get(patologia_es, {
        "alto": NIVEL_ALTO_VISUAL,
        "moderado": NIVEL_MODERADO_VISUAL,
        "leve": NIVEL_LEVE_VISUAL,
    })


def clasificar_para_visualizacion(
    patologia_es: str,
    probabilidad: float,
    detectado_por_modelo: Optional[bool] = None,
    threshold_modelo: Optional[float] = None
) -> NivelVisual:
    """
    Clasifica una probabilidad en nivel VISUAL para frontend.

    Args:
        patologia_es: Nombre de la patología en español
        probabilidad: Probabilidad estimada [0,1]
        detectado_por_modelo: Si el modelo lo detectó (prob >= threshold_modelo)
        threshold_modelo: Threshold de decisión del modelo (del checkpoint)

    Returns:
        NivelVisual con info para UI (color, etiqueta, descripción)
    """
    u = obtener_umbrales_visuales(patologia_es)

    if probabilidad >= u["alto"]:
        return NivelVisual(
            etiqueta="alto",
            color=NIVEL_COLORS["alto"],
            umbral_visual_usado=u["alto"],
            descripcion=f"Probabilidad ≥ {int(u['alto']*100)}%: Prioridad alta para revisión",
            probabilidad=probabilidad,
            detectado_por_modelo=detectado_por_modelo,
            threshold_modelo=threshold_modelo,
        )
    if probabilidad >= u["moderado"]:
        return NivelVisual(
            etiqueta="moderado",
            color=NIVEL_COLORS["moderado"],
            umbral_visual_usado=u["moderado"],
            descripcion=f"Probabilidad {int(u['moderado']*100)}–{int(u['alto']*100)}%: Revisión recomendada",
            probabilidad=probabilidad,
            detectado_por_modelo=detectado_por_modelo,
            threshold_modelo=threshold_modelo,
        )
    if probabilidad >= u["leve"]:
        return NivelVisual(
            etiqueta="leve",
            color=NIVEL_COLORS["leve"],
            umbral_visual_usado=u["leve"],
            descripcion=f"Probabilidad {int(u['leve']*100)}–{int(u['moderado']*100)}%: Considerar seguimiento",
            probabilidad=probabilidad,
            detectado_por_modelo=detectado_por_modelo,
            threshold_modelo=threshold_modelo,
        )
    return NivelVisual(
        etiqueta="marginal",
        color=NIVEL_COLORS["marginal"],
        umbral_visual_usado=u["leve"],
        descripcion=f"Probabilidad < {int(u['leve']*100)}%: No significativo visualmente",
        probabilidad=probabilidad,
        detectado_por_modelo=detectado_por_modelo,
        threshold_modelo=threshold_modelo,
    )


def clasificar_todas_para_visualizacion(
    patologias: Dict[str, float],
    thresholds_modelo: Optional[Dict[str, float]] = None,
    detectados: Optional[Dict[str, bool]] = None
) -> Dict[str, Dict]:
    """
    Clasifica un diccionario completo de patologías → probabilidades para visualización.

    Args:
        patologias: Dict {patologia_es: probabilidad}
        thresholds_modelo: Dict {patologia_en: threshold} del checkpoint (opcional)
        detectados: Dict {patologia_en: bool} si ya se sabe qué detectó el modelo (opcional)

    Returns:
        Dict con info completa para frontend: probabilidad, nivel visual, color,
        detectado_por_modelo, threshold_modelo, etc.
    """
    # Mapeo ES -> EN para buscar thresholds del modelo
    ES_A_EN = {
        "Atelectasia": "Atelectasis",
        "Consolidación": "Consolidation",
        "Edema pulmonar": "Edema",
        "Enfisema": "Emphysema",
        "Derrame pleural": "Effusion",
        "Fibrosis pulmonar": "Fibrosis",
        "Infiltrado pulmonar": "Infiltration",
        "Masa pulmonar": "Mass",
        "Nódulo pulmonar": "Nodule",
        "Engrosamiento pleural": "Pleural_Thickening",
        "Neumonía": "Pneumonia",
        "Neumotórax": "Pneumothorax",
    }

    resultado = {}
    for nombre_es, prob in patologias.items():
        nombre_en = ES_A_EN.get(nombre_es, nombre_es)

        detectado = None
        thresh_modelo = None

        if detectados is not None and nombre_en in detectados:
            detectado = detectados[nombre_en]
        if thresholds_modelo is not None and nombre_en in thresholds_modelo:
            thresh_modelo = thresholds_modelo[nombre_en]
            # Si no nos pasaron detectados pero sí threshold, calcular
            if detectado is None:
                detectado = prob >= thresh_modelo

        nivel = clasificar_para_visualizacion(
            nombre_es, prob,
            detectado_por_modelo=detectado,
            threshold_modelo=thresh_modelo
        )

        resultado[nombre_es] = {
            "probabilidad": prob,
            "nivel": nivel.etiqueta,
            "color": nivel.color,
            "umbral_visual": nivel.umbral_visual_usado,
            "descripcion": nivel.descripcion,
            "etiqueta": NIVEL_LABELS[nivel.etiqueta],
            "detectado_por_modelo": nivel.detectado_por_modelo,
            "threshold_modelo": nivel.threshold_modelo,
        }
    return resultado


def get_api_response() -> Dict:
    """
    Retorna toda la configuración para la API /api/diagnostico/niveles-clinicos/

    Incluye nota explicativa sobre la distinción thresholds_modelo vs niveles_visuales.
    """
    return {
        "niveles_visuales_generales": {
            "alto": NIVEL_ALTO_VISUAL,
            "moderado": NIVEL_MODERADO_VISUAL,
            "leve": NIVEL_LEVE_VISUAL,
        },
        "umbrales_visuales_por_patologia": {
            k: {"alto": v["alto"], "moderado": v["moderado"], "leve": v["leve"]}
            for k, v in UMBRALES_VISUALES_PATOLOGIA.items()
        },
        "labels": NIVEL_LABELS,
        "colors": NIVEL_COLORS,
        "version": "2.0",
        "nota": (
            "IMPORTANTE: Estos son NIVELES DE VISUALIZACIÓN (UI/UX), NO thresholds de decisión del modelo. "
            "Los thresholds de decisión (detección sí/no) provienen del checkpoint del modelo "
            "(optimizados en VALIDATION via Youden's J) y se aplican en DetectorTorax.predecir(). "
            "Este endpoint solo provee codificación de color para el frontend."
        ),
    }


# ──────────────────────────────────────────────────────────────────────────────
# ALIASES DE COMPATIBILIDAD (código existente que use las funciones antiguas)
# ──────────────────────────────────────────────────────────────────────────────

def clasificar_probabilidad(patologia: str, probabilidad: float) -> NivelVisual:
    """
    Alias de compatibilidad - usa clasificar_para_visualizacion.
    """
    return clasificar_para_visualizacion(patologia, probabilidad)


def clasificar_todas(patologias: Dict[str, float]) -> Dict[str, Dict]:
    """
    Alias de compatibilidad - usa clasificar_todas_para_visualizacion.
    """
    return clasificar_todas_para_visualizacion(patologias)
