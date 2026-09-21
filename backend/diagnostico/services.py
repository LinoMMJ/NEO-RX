"""
Servicio de inferencia CNN para radiografías de tórax - proyecto Neo RX.

Modelo: ResNet-50 de torchxrayvision (resnet50-res512-all) — baseline preentrenado
o fine-tuned en NIH ChestX-ray14 (12 patologías pulmonares). La salida se filtra a las
patologías neumológicas relevantes para el área de neumología del centro
Neo Rayos X Digital.

El modelo se carga una sola vez en memoria (patrón singleton) y se reutiliza
en cada inferencia. Si la variable de entorno NEORX_MODEL_PATH apunta a un
checkpoint fine-tuned válido, se carga ese modelo en lugar del baseline.

IMPORTANTE:
- Si NEORX_MODEL_PATH está configurado pero el archivo no existe, se lanza error.
- NO se hace fallback silencioso a baseline.
- Los thresholds de decisión provienen del checkpoint (optimizados en VALIDATION).
- Terminología: "hallazgo detectado", "probabilidad estimada", "resultado preliminar".

Ubicación: backend/diagnostico/services.py
"""

import os
import sys
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms
import torchxrayvision as xrv
import pydicom
from PIL import Image

# Fix Windows: la barra de progreso de descarga de torchxrayvision usa el
# carácter Unicode "█" que crashea en consolas cp1252 (PowerShell/CMD),
# truncando la descarga de los pesos (~90MB) y corrompiendo el checkpoint.
# Forzar UTF-8 evita este problema y permite descargas completas.
if sys.platform == "win32":
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


# Patologías neumológicas del BASELINE (torchxrayvision 18 labels -> 14 ES).
# Se excluyen: Cardiomegaly, Hernia, Fracture, Pneumoperitoneum, Mediastinum.
# "Lung Lesion" se incluye pero no tiene umbral calibrado en estos pesos.
PATOLOGIAS_NEUMOLOGIA_BASELINE = {
    # Infecciones e inflamación pulmonar
    "Pneumonia":          "Neumonía",
    "Consolidation":      "Consolidación",
    "Infiltration":       "Infiltrado pulmonar",
    # Opacidades y lesiones parenquimatosas
    "Lung Opacity":       "Opacidad pulmonar",
    "Lung Lesion":        "Lesión pulmonar",
    # Patología pleural
    "Effusion":           "Derrame pleural",
    "Pneumothorax":       "Neumotórax",
    "Pleural_Thickening": "Engrosamiento pleural",
    # Patología obstructiva e intersticial
    "Atelectasis":        "Atelectasia",
    "Emphysema":          "Enfisema",
    "Fibrosis":           "Fibrosis pulmonar",
    "Edema":              "Edema pulmonar",
    # Lesiones focales (oncológico / TB)
    "Nodule":             "Nódulo pulmonar",
    "Mass":               "Masa pulmonar",
}

# Etiquetas NIH ChestX-ray14 (orden fijo usado en fine-tuning - 14 labels)
NIH_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Effusion",
    "Fibrosis",
    "Hernia",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
]

# Mapeo NIH EN -> ES (coincide con config.yaml labels_es)
NIH_LABELS_ES = {
    "Atelectasis": "Atelectasia",
    "Cardiomegaly": "Cardiomegalia",
    "Consolidation": "Consolidación",
    "Edema": "Edema pulmonar",
    "Emphysema": "Enfisema",
    "Effusion": "Derrame pleural",
    "Fibrosis": "Fibrosis pulmonar",
    "Hernia": "Hernia",
    "Infiltration": "Infiltrado pulmonar",
    "Mass": "Masa pulmonar",
    "Nodule": "Nódulo pulmonar",
    "Pleural_Thickening": "Engrosamiento pleural",
    "Pneumonia": "Neumonía",
    "Pneumothorax": "Neumotórax",
}

# Patologías puramente neumológicas (excluye cardiología y otras) - 12 clases
PULMONARY_LABELS = {
    "Atelectasis",
    "Consolidation",
    "Edema",
    "Emphysema",
    "Effusion",
    "Fibrosis",
    "Infiltration",
    "Mass",
    "Nodule",
    "Pleural_Thickening",
    "Pneumonia",
    "Pneumothorax",
}


class DetectorTorax:
    """Encapsula el modelo CNN y todo el preprocesamiento de la imagen.

    Soporta dos modos:
    - Baseline: torchxrayvision ResNet-50 preentrenado (18 labels)
    - Fine-tuned: checkpoint propio entrenado en NIH ChestX-ray14 (12 labels pulmonares)
      Activado mediante variable de entorno NEORX_MODEL_PATH.

    REGLAS CRÍTICAS:
    - Si NEORX_MODEL_PATH está configurado y el archivo NO existe -> ERROR (no fallback)
    - Thresholds provienen del checkpoint (optimizados en VALIDATION, no en TEST)
    - Terminología: hallazgo detectado / probabilidad estimada / resultado preliminar
    """

    _modelo = None
    _transform = None
    _labels_es = None       # Mapa EN->ES del modelo cargado
    _thresholds = None      # Thresholds por clase (del checkpoint)
    _is_finetuned = False   # True si se cargó checkpoint fine-tuned

    @classmethod
    def cargar(cls):
        """Carga el modelo y los transforms una sola vez (singleton)."""
        if cls._modelo is None:
            # Verificar si hay checkpoint fine-tuned configurado
            checkpoint_path = os.environ.get("NEORX_MODEL_PATH")

            if checkpoint_path:
                # NEORX_MODEL_PATH está configurado -> DEBE existir
                path_obj = Path(checkpoint_path)
                if not path_obj.is_file():
                    raise FileNotFoundError(
                        f"[DetectorTorax] ERROR: NEORX_MODEL_PATH está configurado "
                        f"({checkpoint_path}) pero el archivo NO EXISTE. "
                        f"No se hará fallback a baseline. Verifique la ruta."
                    )
                print(f"[DetectorTorax] Cargando modelo fine-tuned desde {checkpoint_path}")
                cls._cargar_finetuned(checkpoint_path)
            else:
                # NEORX_MODEL_PATH no configurado -> usar baseline
                print("[DetectorTorax] NEORX_MODEL_PATH no configurado. Usando baseline preentrenado.")
                cls._cargar_baseline()
        return cls._modelo

    @classmethod
    def _cargar_baseline(cls):
        """Carga el modelo baseline preentrenado de torchxrayvision.

        Si el checkpoint local está corrupto (descarga truncada por el crash
        de la barra de progreso en Windows), se elimina y se re-descarga.
        """
        # Ruta del checkpoint local de torchxrayvision
        weights_dir = Path.home() / ".torchxrayvision" / "models_data"
        weights_file = weights_dir / "pc-nih-rsna-siim-vin-resnet50-test512-e400-state.pt"

        # Validación de integridad: el archivo completo pesa ~90MB.
        # Si existe pero es sospechosamente pequeño (<50MB), está truncado.
        if weights_file.exists() and weights_file.stat().st_size < 50 * 1024 * 1024:
            print(f"[DetectorTorax] Checkpoint corrupto detectado ({weights_file.stat().st_size} bytes). "
                  f"Eliminando para re-descarga...")
            try:
                weights_file.unlink()
            except OSError:
                pass

        cls._modelo = xrv.models.ResNet(weights="resnet50-res512-all")
        cls._modelo.eval()
        cls._transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(512),
        ])
        cls._labels_es = PATOLOGIAS_NEUMOLOGIA_BASELINE
        cls._thresholds = {label: 0.5 for label in cls._modelo.pathologies}
        cls._is_finetuned = False

    @classmethod
    def _cargar_finetuned(cls, checkpoint_path: str):
        """Carga checkpoint fine-tuned desde disco."""
        try:
            # weights_only=False necesario porque el checkpoint contiene listas/dicts (metadatos)
            ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

            # Instanciar arquitectura base (los pesos se sobreescriben con load_state_dict)
            cls._modelo = xrv.models.ResNet(weights="resnet50-res512-all")

            # Reemplazar cabeza de clasificación para que coincida con el checkpoint
            pathologies = ckpt.get("pathologies", NIH_LABELS)
            in_features = cls._modelo.model.fc.in_features
            cls._modelo.model.fc = nn.Linear(in_features, len(pathologies))

            # Cargar pesos (incluye backbone + fc + op_norm)
            state_dict = ckpt.get("state_dict", ckpt)
            cls._modelo.load_state_dict(state_dict, strict=True)

            # Metadatos para inferencia
            cls._modelo.pathologies = pathologies
            cls._labels_es = ckpt.get("labels_es", NIH_LABELS_ES)

            # Cargar thresholds del checkpoint (optimizados en VALIDATION)
            if "thresholds" in ckpt:
                cls._thresholds = ckpt["thresholds"]
            elif "thresholds_list" in ckpt:
                cls._thresholds = {label: thr for label, thr in zip(pathologies, ckpt["thresholds_list"])}
            else:
                print("[DetectorTorax] WARNING: No thresholds found in checkpoint, using 0.5 default")
                cls._thresholds = {label: 0.5 for label in pathologies}

            cls._is_finetuned = True

            cls._transform = torchvision.transforms.Compose([
                xrv.datasets.XRayCenterCrop(),
                xrv.datasets.XRayResizer(512),
            ])

            cls._modelo.eval()
            print(f"[DetectorTorax] Fine-tuned model loaded from {checkpoint_path}")
            print(f"[DetectorTorax] Classes: {len(pathologies)} | Thresholds loaded: {len(cls._thresholds)}")
            print(f"[DetectorTorax] Thresholds: {cls._thresholds}")

        except Exception as e:
            # NO fallback silencioso - propagar el error
            raise RuntimeError(
                f"[DetectorTorax] ERROR loading fine-tuned checkpoint from {checkpoint_path}: {e}. "
                f"NEORX_MODEL_PATH was set but model failed to load. Check file integrity."
            ) from e

    @staticmethod
    def _a_2d(img):
        """Garantiza una imagen 2D en escala de grises."""
        if img.ndim > 2:
            img = img[:, :, 0]
        return img

    @classmethod
    def _preprocesar(cls, img_2d, maxval):
        """Normaliza al rango [-1024, 1024] y aplica crop + resize."""
        img = xrv.datasets.normalize(img_2d, maxval)   # escala según el bit-depth
        img = img[None, :, :]                          # añade canal -> [1, H, W]
        img = cls._transform(img)                      # -> [1, 512, 512]
        return torch.from_numpy(img).unsqueeze(0)      # tensor [1, 1, 512, 512]

    @classmethod
    def predecir(cls, img_2d, maxval):
        """
        Devuelve dict con hallazgos detectados, probabilidades y thresholds.

        Estructura de retorno:
        {
            "hallazgos": [
                {
                    "etiqueta": "Nódulo pulmonar",
                    "etiqueta_en": "Nodule",
                    "probabilidad_estimada": 0.82,
                    "detectado": true,
                    "threshold_usado": 0.35
                },
                ...
            ],
            "probabilidades": {"Nodule": 0.82, ...},
            "thresholds": {"Nodule": 0.35, ...},
            "modelo": "resnet50_finetuned_nih" | "resnet50_baseline",
            "es_fine_tuned": true/false,
            "nota": "Resultado preliminar - requiere revisión profesional."
        }
        """
        modelo = cls.cargar()
        tensor = cls._preprocesar(cls._a_2d(img_2d), maxval)

        with torch.no_grad():
            # El forward de xrv ya aplica sigmoide (op_norm) -> salida en [0,1]
            salida = modelo(tensor)[0].cpu().numpy()

        probs = dict(zip(modelo.pathologies, salida))
        thresholds = cls._thresholds or {label: 0.5 for label in modelo.pathologies}

        hallazgos = []
        prob_dict = {}
        thresh_dict = {}

        for clave in modelo.pathologies:
            if clave not in probs or np.isnan(probs[clave]):
                continue

            prob = float(probs[clave])
            threshold = float(thresholds.get(clave, 0.5))
            detectado = prob >= threshold

            nombre_es = cls._labels_es.get(clave, clave)

            prob_dict[clave] = prob
            thresh_dict[clave] = threshold

            # Solo incluir patologías pulmonares (excluir Cardiomegaly, Hernia si están presentes)
            if clave in PULMONARY_LABELS:
                hallazgos.append({
                    "etiqueta": nombre_es,
                    "etiqueta_en": clave,
                    "probabilidad_estimada": round(prob, 4),
                    "detectado": bool(detectado),
                    "threshold_usado": round(threshold, 4),
                })

        # Ordenar por probabilidad descendente
        hallazgos.sort(key=lambda x: x["probabilidad_estimada"], reverse=True)

        return {
            "hallazgos": hallazgos,
            "probabilidades": prob_dict,
            "thresholds": thresh_dict,
            "modelo": "resnet50_finetuned_nih" if cls._is_finetuned else "resnet50_baseline",
            "es_fine_tuned": cls._is_finetuned,
            "nota": "Resultado preliminar - requiere revisión profesional. PENDIENTE DE EJECUCIÓN EXPERIMENTAL.",
        }

    @classmethod
    def desde_dicom(cls, ruta_dcm):
        """Lee un DICOM, corrige la inversión MONOCHROME1 y predice."""
        from estudios.utils import leer_dicom
        ds = leer_dicom(ruta_dcm)
        arr = ds.pixel_array.astype(np.float32)
        if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
            arr = arr.max() - arr                      # invierte negativo -> positivo
        bits = getattr(ds, "BitsStored", 12)
        maxval = float(2 ** bits - 1)                  # p.ej. 4095 para 12 bits
        return cls.predecir(arr, maxval)

    @classmethod
    def desde_png(cls, ruta_png):
        """Lee un PNG/JPG de 8 bits en escala de grises y predice."""
        arr = np.array(Image.open(ruta_png).convert("L")).astype(np.float32)
        return cls.predecir(arr, 255.0)
