"""Clasificacion conservadora previa al analisis CNN.

La fuente mas fiable son los metadatos DICOM. Para imagenes raster se usan
rasgos visuales explicables; si no hay evidencia suficiente, la CNN no se
ejecuta. Esta compuerta evita usar el clasificador patologico fuera de dominio.
"""

from dataclasses import asdict, dataclass
import re
import unicodedata

import cv2
import numpy as np
from PIL import Image

from .utils import dicom_pixel_array_2d


XRAY_MODALITIES = {"CR", "DX", "DR", "RG", "RF", "XA", "MG", "IO", "PX"}
NON_XRAY_MODALITIES = {"CT", "MR", "MRI", "US", "NM", "PT", "PET"}

CHEST_TERMS = {
    "CHEST", "THORAX", "TORAX", "LUNG", "PULMON", "RIB", "COSTILLA",
}

REGION_TERMS = {
    "Craneo": {"SKULL", "CRANIUM", "HEAD", "CRANEO"},
    "Mama": {"BREAST", "MAMMO", "MAMMOGRAPHY", "MAMA"},
    "Columna": {"SPINE", "CERVICAL", "THORACIC SPINE", "LUMBAR", "SACRUM", "COLUMNA"},
    "Hombro": {"SHOULDER", "HOMBRO", "CLAVICLE"},
    "Brazo": {"HUMERUS", "ARM", "BRAZO", "FOREARM", "ANTEBRAZO"},
    "Codo": {"ELBOW", "CODO"},
    "Muneca": {"WRIST", "MUNECA", "CARPAL"},
    "Mano": {"HAND", "FINGER", "MANO", "DEDO"},
    "Abdomen": {"ABDOMEN", "ABDOMINAL", "KUB"},
    "Pelvis": {"PELVIS", "HIP", "CADERA"},
    "Femur": {"FEMUR", "THIGH", "MUSLO"},
    "Rodilla": {"KNEE", "RODILLA"},
    "Pierna": {"TIBIA", "FIBULA", "LEG", "PIERNA"},
    "Tobillo": {"ANKLE", "TOBILLO"},
    "Pie": {"FOOT", "TOE", "PIE"},
}


@dataclass(frozen=True)
class ImageSuitability:
    classification: str
    is_radiograph: bool
    cnn_eligible: bool
    anatomical_region: str
    confidence: float
    source: str
    reason: str
    features: dict

    def to_dict(self):
        return asdict(self)


def _normalise_text(value):
    value = unicodedata.normalize("NFKD", str(value or ""))
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", value.upper()).strip()


def _dicom_description(dataset):
    fields = [
        "BodyPartExamined", "StudyDescription", "SeriesDescription",
        "ProtocolName", "RequestedProcedureDescription",
    ]
    return " ".join(_normalise_text(getattr(dataset, field, "")) for field in fields).strip()


def _detect_region(text):
    tokens = f" {text} "
    if any(f" {term} " in tokens for term in CHEST_TERMS):
        return "Torax"
    for region, terms in REGION_TERMS.items():
        if any(f" {term} " in tokens for term in terms):
            return region
    return ""


def _entropy(gray):
    hist = cv2.calcHist([(gray * 255).astype(np.uint8)], [0], None, [256], [0, 256]).ravel()
    probabilities = hist / max(float(hist.sum()), 1.0)
    probabilities = probabilities[probabilities > 0]
    return float(-(probabilities * np.log2(probabilities)).sum())


def _visual_features(image):
    if isinstance(image, Image.Image):
        rgb = np.asarray(image.convert("RGB").resize((256, 256)), dtype=np.float32) / 255.0
        original_width, original_height = image.size
        channel_correlations = []
        for first, second in ((0, 1), (0, 2), (1, 2)):
            a = rgb[:, :, first].ravel()
            b = rgb[:, :, second].ravel()
            if float(a.std()) < 1e-6 or float(b.std()) < 1e-6:
                channel_correlations.append(1.0 if np.allclose(a, b) else 0.0)
            else:
                channel_correlations.append(float(np.corrcoef(a, b)[0, 1]))
        channel_correlation = min(channel_correlations)
        chroma = np.max(rgb, axis=2) - np.min(rgb, axis=2)
        grayscale_fraction = float((chroma < 0.08).mean())
        gray = cv2.cvtColor((rgb * 255).astype(np.uint8), cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
    else:
        array = np.asarray(image, dtype=np.float32)
        while array.ndim > 2:
            array = array[0]
        original_height, original_width = array.shape
        low, high = np.percentile(array, [1, 99])
        gray = np.clip((array - low) / (high - low + 1e-6), 0, 1)
        gray = cv2.resize(gray, (256, 256), interpolation=cv2.INTER_AREA)
        channel_correlation = 1.0
        grayscale_fraction = 1.0

    low, high = np.percentile(gray, [2, 98])
    dynamic_range = float(high - low)
    normalized = np.clip((gray - low) / (dynamic_range + 1e-6), 0, 1)

    left = normalized[35:210, 25:110]
    right = np.fliplr(normalized[35:210, 146:231])
    if float(left.std()) < 1e-6 or float(right.std()) < 1e-6:
        symmetry = 0.0
    else:
        symmetry = float(np.corrcoef(left.ravel(), right.ravel())[0, 1])

    lung_mean = float(
        (normalized[55:205, 25:105].mean() + normalized[55:205, 151:231].mean()) / 2
    )
    central_contrast = float(normalized[55:205, 108:148].mean() - lung_mean)
    edge_density = float((cv2.Canny((normalized * 255).astype(np.uint8), 40, 120) > 0).mean())
    entropy = _entropy(normalized)
    aspect_ratio = float(original_width / max(original_height, 1))

    return {
        "channel_correlation": round(channel_correlation, 4),
        "grayscale_fraction": round(grayscale_fraction, 4),
        "dynamic_range": round(dynamic_range, 4),
        "symmetry": round(symmetry, 4),
        "central_contrast": round(central_contrast, 4),
        "edge_density": round(edge_density, 4),
        "entropy": round(entropy, 4),
        "aspect_ratio": round(aspect_ratio, 4),
    }


def _classify_visual(image, source="visual_analysis", confirmed_xray=False):
    features = _visual_features(image)
    radiograph_score = 0.0
    if features["channel_correlation"] >= 0.90:
        radiograph_score += 0.35
    if features["grayscale_fraction"] >= 0.75 or features["channel_correlation"] >= 0.96:
        radiograph_score += 0.20
    if features["dynamic_range"] >= 0.35:
        radiograph_score += 0.20
    if features["entropy"] >= 4.5:
        radiograph_score += 0.15
    if 0.025 <= features["edge_density"] <= 0.38:
        radiograph_score += 0.10

    aspect_ok = 0.55 <= features["aspect_ratio"] <= 1.85
    chest_pattern = (
        features["symmetry"] >= 0.12
        and features["central_contrast"] >= 0.05
        and aspect_ok
    )
    chest_score = (
        min(max((features["symmetry"] + 0.10) / 0.80, 0.0), 1.0) * 0.45
        + min(max(features["central_contrast"] / 0.35, 0.0), 1.0) * 0.40
        + (0.15 if aspect_ok else 0.0)
    )
    features["radiograph_score"] = round(radiograph_score, 4)
    features["chest_score"] = round(chest_score, 4)

    if radiograph_score >= 0.72 and chest_pattern and chest_score >= 0.48:
        return ImageSuitability(
            "chest_xray", True, True, "Torax",
            round(min(0.99, 0.55 * radiograph_score + 0.45 * chest_score), 4),
            source,
            "La imagen presenta un patron radiografico toracico compatible.",
            features,
        )

    if confirmed_xray or radiograph_score >= 0.82:
        return ImageSuitability(
            "other_xray", True, False, "No determinada",
            round(max(0.60, radiograph_score), 4),
            source,
            "Es una radiografia, pero no hay evidencia suficiente de que corresponda al torax.",
            features,
        )

    return ImageSuitability(
        "not_xray", False, False, "",
        round(max(0.55, 1.0 - radiograph_score), 4),
        source,
        "La imagen no presenta caracteristicas suficientes de una radiografia diagnostica.",
        features,
    )


def classify_medical_image(validation_result):
    """Clasifica el archivo ya validado sin ejecutar el modelo patologico."""
    file_type = validation_result.get("file_type")
    if file_type == "dicom":
        dataset = validation_result.get("dataset")
        modality = _normalise_text(getattr(dataset, "Modality", ""))
        description = _dicom_description(dataset)
        region = _detect_region(description)
        metadata_features = {"modality": modality, "description": description[:300]}

        if modality in NON_XRAY_MODALITIES:
            return ImageSuitability(
                "not_xray", False, False, region, 0.99, "dicom_metadata",
                f"La modalidad DICOM {modality} no corresponde a una radiografia convencional.",
                metadata_features,
            )
        if region == "Torax" and (not modality or modality in XRAY_MODALITIES):
            return ImageSuitability(
                "chest_xray", True, True, "Torax", 0.99, "dicom_metadata",
                "Los metadatos DICOM identifican una radiografia de torax.",
                metadata_features,
            )
        if region and region != "Torax" and (not modality or modality in XRAY_MODALITIES):
            return ImageSuitability(
                "other_xray", True, False, region, 0.98, "dicom_metadata",
                f"Los metadatos DICOM identifican una radiografia de {region.lower()}.",
                metadata_features,
            )

        pixels = dicom_pixel_array_2d(dataset)
        visual = _classify_visual(
            pixels,
            source="dicom_pixels",
            confirmed_xray=modality in XRAY_MODALITIES,
        )
        merged = dict(visual.features)
        merged.update(metadata_features)
        return ImageSuitability(
            visual.classification,
            visual.is_radiograph,
            visual.cnn_eligible,
            visual.anatomical_region,
            visual.confidence,
            visual.source,
            visual.reason,
            merged,
        )

    image = validation_result.get("pil_image")
    if image is None:
        return ImageSuitability(
            "not_xray", False, False, "", 1.0, "file_validation",
            "No se pudo obtener una imagen valida para clasificar.", {},
        )
    return _classify_visual(image)
