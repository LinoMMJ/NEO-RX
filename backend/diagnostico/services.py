"""
Servicio de inferencia CNN para radiografias de torax - proyecto Neo RX.

Modelo: ResNet-50 de torchxrayvision (resnet50-res512-all) — baseline preentrenado
o fine-tuned en NIH ChestX-ray14 (14 patologias). La salida se filtra a las
patologias neumologicas relevantes para el area de neumologia del centro
Neo Rayos X Digital.

El modelo se carga una sola vez en memoria (patron singleton) y se reutiliza
en cada inferencia. Si la variable de entorno NEORX_MODEL_PATH apunta a un
checkpoint fine-tuned valido, se carga ese modelo en lugar del baseline.

Ubicacion sugerida: backend/diagnostico/services.py
"""

import os
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms
import torchxrayvision as xrv
import pydicom
from PIL import Image


# Patologias neumologicas del BASELINE (torchxrayvision 18 labels -> 14 ES).
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

# Etiquetas NIH ChestX-ray14 (orden fijo usado en fine-tuning)
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

# Patologias puramente neumologicas (excluye cardiología y otras)
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
    - Fine-tuned: checkpoint propio entrenado en NIH ChestX-ray14 (14 labels)
      Activado mediante variable de entorno NEORX_MODEL_PATH.
    """

    _modelo = None
    _transform = None
    _labels_es = None       # Mapa EN->ES del modelo cargado
    _is_finetuned = False   # True si se cargo checkpoint fine-tuned

    @classmethod
    def cargar(cls):
        """Carga el modelo y los transforms una sola vez (singleton)."""
        if cls._modelo is None:
            # Verificar si hay checkpoint fine-tuned configurado
            checkpoint_path = os.environ.get("NEORX_MODEL_PATH")
            if checkpoint_path and os.path.isfile(checkpoint_path):
                cls._cargar_finetuned(checkpoint_path)
            else:
                cls._cargar_baseline()
        return cls._modelo

    @classmethod
    def _cargar_baseline(cls):
        """Carga el modelo baseline preentrenado de torchxrayvision."""
        cls._modelo = xrv.models.ResNet(weights="resnet50-res512-all")
        cls._modelo.eval()
        cls._transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(512),
        ])
        cls._labels_es = PATOLOGIAS_NEUMOLOGIA_BASELINE
        cls._is_finetuned = False

    @classmethod
    def _cargar_finetuned(cls, checkpoint_path: str):
        """Carga checkpoint fine-tuned desde disco."""
        try:
            # weights_only=False necesario porque el checkpoint contiene listas/dicts (metadatos)
            ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

            # Instanciar arquitectura base (los pesos se sobreescriben con load_state_dict)
            cls._modelo = xrv.models.ResNet(weights="resnet50-res512-all")

            # Reemplazar cabeza de clasificacion para que coincida con el checkpoint
            pathologies = ckpt.get("pathologies", NIH_LABELS)
            in_features = cls._modelo.model.fc.in_features
            cls._modelo.model.fc = nn.Linear(in_features, len(pathologies))

            # Cargar pesos (incluye backbone + fc + op_norm)
            state_dict = ckpt.get("state_dict", ckpt)
            cls._modelo.load_state_dict(state_dict, strict=True)

            # Metadatos para inferencia
            cls._modelo.pathologies = pathologies
            cls._labels_es = ckpt.get("labels_es", NIH_LABELS_ES)
            cls._is_finetuned = True

            cls._transform = torchvision.transforms.Compose([
                xrv.datasets.XRayCenterCrop(),
                xrv.datasets.XRayResizer(512),
            ])

            cls._modelo.eval()
            print(f"[DetectorTorax] Fine-tuned model loaded from {checkpoint_path}")
            print(f"[DetectorTorax] Classes: {len(pathologies)} | Pulmonary-only: {len(PULMONARY_LABELS)}")

        except Exception as e:
            print(f"[DetectorTorax] ERROR loading fine-tuned checkpoint: {e}")
            print("[DetectorTorax] Falling back to baseline model...")
            cls._cargar_baseline()

    @staticmethod
    def _a_2d(img):
        """Garantiza una imagen 2D en escala de grises."""
        if img.ndim > 2:
            img = img[:, :, 0]
        return img

    @classmethod
    def _preprocesar(cls, img_2d, maxval):
        """Normaliza al rango [-1024, 1024] y aplica crop + resize."""
        img = xrv.datasets.normalize(img_2d, maxval)   # escala segun el bit-depth
        img = img[None, :, :]                          # anade canal -> [1, H, W]
        img = cls._transform(img)                      # -> [1, 512, 512]
        return torch.from_numpy(img).unsqueeze(0)      # tensor [1, 1, 512, 512]

    @classmethod
    def predecir(cls, img_2d, maxval):
        """Devuelve {patologia_es: probabilidad} ordenado de mayor a menor,
        solo con las patologias neumologicas (baseline 14, fine-tuned 12)."""
        modelo = cls.cargar()
        tensor = cls._preprocesar(cls._a_2d(img_2d), maxval)
        with torch.no_grad():
            # El forward de xrv ya aplica sigmoide (op_norm) -> salida en [0,1]
            salida = modelo(tensor)[0].cpu().numpy()

        probs = dict(zip(modelo.pathologies, salida))

        if cls._is_finetuned:
            # Modelo fine-tuned: 14 labels NIH -> mapear EN->ES y filtrar solo neumologicas
            resultado = {
                cls._labels_es[clave]: round(float(probs[clave]), 4)
                for clave in modelo.pathologies
                if clave in probs
                and not np.isnan(probs[clave])
                and clave in PULMONARY_LABELS
                and clave in cls._labels_es
            }
        else:
            # Baseline: 18 labels -> filtrar a las 14 neumologicas definidas
            resultado = {
                nombre_es: round(float(probs[clave]), 4)
                for clave, nombre_es in PATOLOGIAS_NEUMOLOGIA_BASELINE.items()
                if clave in probs and not np.isnan(probs[clave])
            }

        return dict(sorted(resultado.items(), key=lambda kv: kv[1], reverse=True))

    @classmethod
    def desde_dicom(cls, ruta_dcm):
        """Lee un DICOM, corrige la inversion MONOCHROME1 y predice."""
        ds = pydicom.dcmread(ruta_dcm)
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
