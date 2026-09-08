import time
import logging
from celery import shared_task

from estudios.models import ImagenDICOM
from .models import ResultadoCNN
from .services import DetectorTorax

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def procesar_imagen_cnn(self, imagen_id):
    """
    Ejecuta la inferencia CNN en background.
    No bloquea el request HTTP — Django responde 202 inmediatamente
    y el frontend hace polling hasta que esta tarea complete.
    """
    imagen = None
    try:
        imagen = ImagenDICOM.objects.get(pk=imagen_id)
        logger.info(f"[CNN TASK {self.request.id}] Procesando imagen #{imagen_id}...")

        ruta = str(imagen.archivo_dicom.path)
        es_dicom = ruta.lower().endswith(('.dcm', '.dicom'))

        t0 = time.time()
        resultado = DetectorTorax.desde_dicom(ruta) if es_dicom else DetectorTorax.desde_png(ruta)
        tiempo = round(time.time() - t0, 3)

        res_cnn, _ = ResultadoCNN.objects.update_or_create(
            imagen=imagen,
            defaults={'patologias': resultado, 'tiempo_inferencia_seg': tiempo},
        )
        imagen.estado_procesamiento = 'procesado'
        imagen.save()

        logger.info(f"[CNN TASK {self.request.id}] Completado en {tiempo}s")
        return {
            'imagen_id': imagen_id,
            'resultado_id': res_cnn.id,
            'patologias': resultado,
            'tiempo_inferencia_seg': tiempo,
        }

    except Exception as e:
        logger.error(f"[CNN TASK {self.request.id}] Error: {e}")
        if imagen is not None:
            try:
                imagen.estado_procesamiento = 'error'
                imagen.save()
            except Exception:
                pass
        raise
