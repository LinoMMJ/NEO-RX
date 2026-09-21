import cv2
import numpy as np
import pydicom

_DESC_PROYECCION = {
    "PA": "Postero-Anterior",
    "AP": "Antero-Posterior",
    "LAT": "Lateral",
}


def leer_dicom(ruta, force=False):
    """Lee un archivo DICOM de forma robusta.

    Algunos archivos .dcm/.dicom exportados por software propietario (como el
    del centro Neo Rayos X) no incluyen el prefijo 'DICM' del File Meta
    Information header. pydicom.dcmread() falla con:
        "File is missing DICOM File Meta Information header or the 'DICM'
         prefix is missing from the header."

    Esta funcion intenta la lectura normal y, si falla por el encabezado,
    reintenta con force=True (permite leer datasets sin meta header).
    """
    try:
        return pydicom.dcmread(ruta, force=force)
    except Exception:
        # Si fallo sin force (o con force) por header faltante, reintentar con force
        return pydicom.dcmread(ruta, force=True)


def detect_projection_type(ruta_dcm_o_metadata):
    """Detecta el tipo de proyección de la radiografía de tórax.

    Tipos:
      PA  = Postero-Anterior (paciente de pie, haz de atrás a adelante)
      AP  = Antero-Posterior (acostado/sentado, portátil)
      LAT = Lateral (proyección de perfil)

    Prioridad 1: tag DICOM ViewPosition (0018,5101).
    Prioridad 2 (PNG o sin tag): inferencia por aspect ratio + distribución
    de brillo.

    Retorna dict: {tipo, fuente, descripcion, confianza}.
    """
    ruta = str(ruta_dcm_o_metadata)
    es_dicom = ruta.lower().endswith((".dcm", ".dicom"))

    # ── Prioridad 1: tag DICOM ViewPosition ──
    if es_dicom:
        try:
            ds = leer_dicom(ruta)
            view = str(getattr(ds, "ViewPosition", "") or "").strip().upper()
            mapa = {
                "PA": "PA", "AP": "AP",
                "LL": "LAT", "RL": "LAT", "LAT": "LAT", "L": "LAT", "LATERAL": "LAT",
            }
            if view in mapa:
                tipo = mapa[view]
                return {
                    "tipo": tipo,
                    "fuente": "dicom_tag",
                    "descripcion": _DESC_PROYECCION[tipo],
                    "confianza": "alta",
                }
        except Exception:
            pass  # cae a inferencia

    # ── Prioridad 2: inferencia por la imagen ──
    try:
        if es_dicom:
            ds = leer_dicom(ruta)
            arr = ds.pixel_array.astype(np.float32)
            if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
                arr = arr.max() - arr
            if arr.ndim > 2:
                arr = arr[:, :, 0]
        else:
            arr = cv2.imread(ruta, cv2.IMREAD_GRAYSCALE)
            if arr is None:
                raise ValueError("No se pudo leer la imagen para inferir proyección.")
            arr = arr.astype(np.float32)

        h, w = arr.shape[:2]
        ratio = w / h if h else 1.0

        # Una proyección lateral suele ser más estrecha (perfil).
        if ratio < 0.7:
            return {
                "tipo": "LAT",
                "fuente": "inferencia",
                "descripcion": _DESC_PROYECCION["LAT"],
                "confianza": "media",
            }

        # Distinguir PA de AP: en AP (portátil) la silueta cardíaca se
        # magnifica y el corazón ocupa más ancho en el tercio inferior.
        norm = (arr - arr.min()) / (arr.max() - arr.min() + 1e-8)
        tercio = h // 3
        brillo_superior = float(norm[:tercio, :].mean())
        brillo_inferior = float(norm[2 * tercio:, :].mean())

        # Mediastino más angosto / campos pulmonares más claros arriba → PA.
        if brillo_superior >= brillo_inferior:
            tipo = "PA"
        else:
            tipo = "AP"

        return {
            "tipo": tipo,
            "fuente": "inferencia",
            "descripcion": _DESC_PROYECCION[tipo],
            "confianza": "media",
        }
    except Exception:
        # Fallback seguro: asumir PA (la proyección estándar de tórax).
        return {
            "tipo": "PA",
            "fuente": "inferencia",
            "descripcion": _DESC_PROYECCION["PA"],
            "confianza": "media",
        }


def calcular_borrosidad(ruta_imagen, umbral=100.0):
    """Retorna (es_nitida: bool, varianza: float) usando cv2.Laplacian.
    Funciona con PNG y con DICOM (convierte pixel_array a escala de grises).
    Una varianza menor al umbral indica borrosidad cinética."""
    ruta = str(ruta_imagen)
    if ruta.lower().endswith(".dcm"):
        ds = leer_dicom(ruta)
        arr = ds.pixel_array.astype(np.float32)
        arr = (arr - arr.min()) / (arr.max() - arr.min() + 1e-8) * 255
        imagen_gris = arr.astype(np.uint8)
        if imagen_gris.ndim > 2:
            imagen_gris = imagen_gris[:, :, 0]
    else:
        imagen_gris = cv2.imread(ruta, cv2.IMREAD_GRAYSCALE)
        if imagen_gris is None:
            raise ValueError(f"No se pudo leer la imagen: {ruta}")

    laplaciano = cv2.Laplacian(imagen_gris, cv2.CV_64F)
    varianza = round(float(laplaciano.var()), 2)
    return varianza >= umbral, varianza
