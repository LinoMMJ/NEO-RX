import time
import logging
from celery import shared_task

from estudios.models import ImagenDICOM
from .models import ResultadoCNN
from .results import probabilities_es
from neorx.models import log_audit
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

        if not imagen.apta_para_cnn or imagen.clasificacion_imagen != "chest_xray":
            imagen.estado_procesamiento = "sin_analisis"
            imagen.motivo_no_cnn = imagen.motivo_no_cnn or "La imagen no es elegible para la CNN de tórax."
            imagen.save(update_fields=["estado_procesamiento", "motivo_no_cnn"])
            return {
                "status": "STORED",
                "imagen_id": imagen_id,
                "estudio_id": imagen.estudio_id,
                "mensaje": "Radiografía almacenada sin análisis CNN.",
            }

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
        imagen.save(update_fields=["estado_procesamiento"])

        from informes.services import create_ai_draft_report
        informe, _ = create_ai_draft_report(imagen.estudio, imagen, res_cnn)

        log_audit(None, action="process", resource_type="resultado_cnn", resource_id=str(res_cnn.pk),
                  metadata={"imagen_id": imagen_id, "estado": "procesado"})
        logger.info(f"[CNN TASK {self.request.id}] Completado en {tiempo}s")
        return {
            'imagen_id': imagen_id,
            'resultado_id': res_cnn.id,
            'estudio_id': imagen.estudio_id,
            'informe_id': informe.id,
            'informe_estado': informe.estado,
            'patologias': probabilities_es(resultado),
            'tiempo_inferencia_seg': tiempo,
            'modelo': resultado.get('modelo', 'cnn'),
            'es_fine_tuned': bool(resultado.get('es_fine_tuned', False)),
            'resolucion_entrada': DetectorTorax._input_size,
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
