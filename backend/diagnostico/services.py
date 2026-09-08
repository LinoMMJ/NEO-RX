"""
Servicio de inferencia CNN para radiografias de torax - proyecto Neo RX.

Modelo: ResNet-50 preentrenado de torchxrayvision (resnet50-res512-all),
entrenado a 512x512 sobre los datasets PadChest, NIH, RSNA, SIIM y VinBigData.
La salida de 18 patologias se FILTRA a las relevantes para el area de
neumologia del centro Neo Rayos X Digital.

El modelo se carga una sola vez en memoria (patron singleton) y se reutiliza
en cada inferencia, tal como define la arquitectura del proyecto. La primera
vez que se ejecuta, descarga los pesos (~100 MB) a ~/.torchxrayvision/.

Ubicacion sugerida: backend/diagnostico/services.py
"""

import numpy as np
import torch
import torchvision.transforms
import torchxrayvision as xrv
import pydicom
from PIL import Image


# De las 18 patologias que devuelve el modelo, nos quedamos solo con las
# neumologicas, mapeadas a su nombre clinico en espanol. Se excluyen las no
# pulmonares (cardiomegalia, hernia, fractura, mediastino) y "Lung Lesion",
# que no tiene umbral de operacion calibrado en este conjunto de pesos.
PATOLOGIAS_NEUMOLOGIA = {
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


class DetectorTorax:
    """Encapsula el modelo CNN y todo el preprocesamiento de la imagen."""

    _modelo = None
    _transform = None

    @classmethod
    def cargar(cls):
        """Carga el modelo y los transforms una sola vez."""
        if cls._modelo is None:
            cls._modelo = xrv.models.ResNet(weights="resnet50-res512-all")
            cls._modelo.eval()
            cls._transform = torchvision.transforms.Compose([
                xrv.datasets.XRayCenterCrop(),     # recorte central -> imagen cuadrada
                xrv.datasets.XRayResizer(512),     # 512x512 = resolucion de entrenamiento
            ])
        return cls._modelo

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
        solo con las patologias neumologicas."""
        modelo = cls.cargar()
        tensor = cls._preprocesar(cls._a_2d(img_2d), maxval)
        with torch.no_grad():
            # 18 probabilidades ya calibradas en [0, 1] (sigmoide + op_norm
            # se aplican dentro del forward al cargar los pesos)
            salida = modelo(tensor)[0].cpu().numpy()
        probs = dict(zip(modelo.pathologies, salida))
        resultado = {
            nombre_es: round(float(probs[clave]), 4)
            for clave, nombre_es in PATOLOGIAS_NEUMOLOGIA.items()
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
