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
import threading
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
import torchvision.models
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


class _ResNet50FineTuned(nn.Module):
    """Local checkpoint architecture without downloading additional weights."""

    def __init__(self, num_classes, op_threshs=None):
        super().__init__()
        self.model = torchvision.models.resnet50(weights=None, num_classes=num_classes)
        self.model.conv1 = nn.Conv2d(
            1, 64, kernel_size=7, stride=2, padding=3, bias=False
        )
        if op_threshs is not None:
            # This buffer is part of the original TorchXRayVision checkpoint,
            # although fine-tuned inference uses raw logits followed by sigmoid.
            self.register_buffer("op_threshs", torch.empty_like(op_threshs))
        self.pathologies = []

    def forward(self, tensor):
        return self.model(tensor)


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
    _ready = False
    _input_size = 512
    _model_name = ""
    _config_key = None
    _load_lock = threading.Lock()
    # PyTorch ejecutando varias ResNet-50 a la vez en CPU degrada mucho el
    # rendimiento: cada solicitud compite por los mismos hilos y termina
    # tardando más que una sola ejecución ordenada.  El servidor de desarrollo
    # puede atender solicitudes concurrentes, por lo que protegemos únicamente
    # la pasada del modelo; el resto del upload continúa siendo concurrente.
    _inference_lock = threading.Lock()

    @staticmethod
    def _finetuned_input_size() -> int:
        """Resuelve una entrada compatible para el checkpoint propio.

        El checkpoint NIH se entrenó a 512 px. Otras dimensiones se admiten
        para experimentos, pero cambian las puntuaciones y requieren validar
        de nuevo los umbrales; no son una optimización clínica equivalente.
        """
        raw_value = os.environ.get("NEORX_INPUT_SIZE", "512")
        try:
            size = int(raw_value)
        except (TypeError, ValueError):
            size = 512
        if size not in {224, 256, 512}:
            print(f"[DetectorTorax] NEORX_INPUT_SIZE={raw_value!r} no válido; se usará 512.")
            return 512
        return size

    @classmethod
    def cargar(cls):
        """Carga y precalienta el modelo una sola vez de forma segura."""
        checkpoint_path = os.environ.get("NEORX_MODEL_PATH")
        baseline_name = os.environ.get("NEORX_BASELINE_WEIGHTS", "densenet121-res224-all")
        cache_path = os.environ.get("NEORX_MODEL_CACHE", "")
        revision = None
        if checkpoint_path and Path(checkpoint_path).is_file():
            revision = Path(checkpoint_path).stat().st_mtime_ns
        config_key = (checkpoint_path or "", revision, baseline_name, cache_path,
                      cls._finetuned_input_size())
        if cls._ready and cls._config_key == config_key:
            return cls._modelo

        with cls._load_lock:
            if cls._ready and cls._config_key == config_key:
                return cls._modelo
            cls._ready = False
            cls._modelo = None
            try:
                threads = max(
                    1,
                    int(os.environ.get("NEORX_TORCH_THREADS", min(4, os.cpu_count() or 1))),
                )
                torch.set_num_threads(threads)
                torch.backends.mkldnn.enabled = True
                if checkpoint_path:
                    path_obj = Path(checkpoint_path)
                    if not path_obj.is_file():
                        raise FileNotFoundError(
                            f"[DetectorTorax] ERROR: NEORX_MODEL_PATH está configurado "
                            f"({checkpoint_path}) pero el archivo NO EXISTE."
                        )
                    print(f"[DetectorTorax] Cargando modelo fine-tuned desde {checkpoint_path}")
                    cls._cargar_finetuned(checkpoint_path)
                else:
                    print("[DetectorTorax] Usando baseline preentrenado local de respuesta rápida.")
                    cls._cargar_baseline()
                cls._precalentar()
                cls._config_key = config_key
                cls._ready = True
            except Exception:
                cls._modelo = None
                cls._transform = None
                cls._ready = False
                cls._config_key = None
                raise
        return cls._modelo

    @classmethod
    def _cargar_baseline(cls):
        """Carga el baseline gratuito desde backend/models (ignorado por Git)."""
        model_name = os.environ.get("NEORX_BASELINE_WEIGHTS", "densenet121-res224-all")
        cache_dir = Path(os.environ.get(
            "NEORX_MODEL_CACHE",
            Path(__file__).resolve().parent.parent / "models",
        ))
        cache_dir.mkdir(parents=True, exist_ok=True)

        threads = max(1, int(os.environ.get("NEORX_TORCH_THREADS", min(8, os.cpu_count() or 1))))
        torch.set_num_threads(threads)
        torch.backends.mkldnn.enabled = True

        if model_name.startswith("densenet"):
            cls._modelo = xrv.models.DenseNet(weights=model_name, cache_dir=str(cache_dir))
        elif model_name.startswith("resnet"):
            cls._modelo = xrv.models.ResNet(weights=model_name, cache_dir=str(cache_dir))
        else:
            raise ValueError(f"Modelo baseline no soportado: {model_name}")

        cls._modelo.eval()
        cls._input_size = 512 if "res512" in model_name else 224
        cls._transform = torchvision.transforms.Compose([
            xrv.datasets.XRayCenterCrop(),
            xrv.datasets.XRayResizer(cls._input_size),
        ])
        cls._labels_es = PATOLOGIAS_NEUMOLOGIA_BASELINE
        cls._thresholds = {label: 0.5 for label in cls._modelo.pathologies}
        cls._is_finetuned = False
        cls._model_name = model_name
        print(f"[DetectorTorax] {model_name} listo ({cls._input_size}px, {threads} hilos CPU).")

    @classmethod
    def _cargar_finetuned(cls, checkpoint_path: str):
        """Carga checkpoint fine-tuned desde disco."""
        try:
            # weights_only=False necesario porque el checkpoint contiene listas/dicts (metadatos)
            ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=False)

            pathologies = ckpt.get("pathologies", NIH_LABELS)
            state_dict = ckpt.get("state_dict", ckpt)
            op_threshs = state_dict.get("op_threshs")

            # The checkpoint already contains the backbone and classification head.
            # Build only the empty architecture to avoid downloading or mixing weights.
            cls._modelo = _ResNet50FineTuned(len(pathologies), op_threshs=op_threshs)
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

            cls._input_size = cls._finetuned_input_size()
            cls._model_name = "resnet50_finetuned_nih"
            cls._transform = torchvision.transforms.Compose([
                xrv.datasets.XRayCenterCrop(),
                xrv.datasets.XRayResizer(cls._input_size),
            ])

            cls._modelo.eval()
            # Channels-last improves CPU convolution layout without changing
            # resolution, weights, thresholds or numerical precision.
            cls._modelo.to(memory_format=torch.channels_last)
            print(f"[DetectorTorax] Fine-tuned model loaded from {checkpoint_path}")
            print(f"[DetectorTorax] Classes: {len(pathologies)} | Thresholds loaded: {len(cls._thresholds)}")
            print(f"[DetectorTorax] Thresholds: {cls._thresholds}")

        except Exception as e:
            # NO fallback silencioso - propagar el error
            raise RuntimeError(
                f"[DetectorTorax] ERROR loading fine-tuned checkpoint from {checkpoint_path}: {e}. "
                f"NEORX_MODEL_PATH was set but model failed to load. Check file integrity."
            ) from e

    @classmethod
    def _precalentar(cls):
        """Ejecuta una pasada vacía para que la primera radiografía sea rápida."""
        sample = torch.linspace(-1024.0, 1024.0, cls._input_size * cls._input_size, dtype=torch.float32).reshape(1, 1, cls._input_size, cls._input_size)
        with torch.inference_mode():
            cls._modelo(sample)

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
        img = cls._transform(img)                      # -> [1, tamaño, tamaño]
        return torch.from_numpy(img).unsqueeze(0).contiguous(memory_format=torch.channels_last)

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

        # Una CNN compartida no debe competir consigo misma por los hilos de
        # CPU. Esto mantiene estable el tiempo por estudio cuando llegan dos
        # cargas casi al mismo tiempo y evita que el cliente agote su espera.
        with cls._inference_lock, torch.inference_mode():
            from .gradcam import GeneradorGradCAM
            output = GeneradorGradCAM.forward(modelo, tensor)
            # Kaggle training and evaluation used raw logits plus sigmoid.
            if cls._is_finetuned:
                output = torch.sigmoid(output)
            salida = output[0].cpu().numpy()

        if not np.isfinite(salida).all():
            raise ValueError("La CNN produjo valores no finitos; no se puede interpretar este resultado.")
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
                    "probabilidad_estimada": prob,
                    "detectado": bool(detectado),
                    "threshold_usado": threshold,
                })

        # Ordenar por probabilidad descendente
        hallazgos.sort(key=lambda x: x["probabilidad_estimada"], reverse=True)

        advertencias = []
        if cls._is_finetuned and cls._input_size != 512:
            advertencias.append("Resolución distinta de los 512 px del entrenamiento; las puntuaciones requieren reevaluación.")
        if sum(float(value) >= 0.995 for value in salida) >= 2:
            advertencias.append("Salida saturada en varias clases. Revisar imagen y dominio de adquisición; no equivale a certeza diagnóstica.")
        return {
            "hallazgos": hallazgos,
            "probabilidades": prob_dict,
            "thresholds": thresh_dict,
            "modelo": cls._model_name,
            "es_fine_tuned": cls._is_finetuned,
            "resolucion_entrada": cls._input_size,
            "advertencias": advertencias,
            "puntuaciones_calibradas": False,
            "nota": "Resultado preliminar de apoyo; requiere revisión profesional.",
        }

    @classmethod
    def desde_dicom(cls, ruta_dcm):
        """Lee un DICOM, corrige la inversión MONOCHROME1 y predice."""
        from estudios.utils import dicom_display_pixels, leer_dicom
        ds = leer_dicom(ruta_dcm)
        return cls.predecir(dicom_display_pixels(ds).astype(np.float32), 255.0)

    @classmethod
    def desde_png(cls, ruta_png):
        """Lee un PNG/JPG de 8 bits en escala de grises y predice."""
        arr = np.array(Image.open(ruta_png).convert("L")).astype(np.float32)
        return cls.predecir(arr, 255.0)
