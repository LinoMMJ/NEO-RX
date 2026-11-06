"""Small development queue used when Redis/Celery are not running locally."""
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

from django.db import close_old_connections

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="neorx-cnn")
_pending = set()
_pending_lock = Lock()


def prepare_local_inference():
    """Load dependencies and warm the CNN in the same thread that scans images."""
    def prepare():
        from .tasks import DetectorTorax
        return DetectorTorax.cargar()
    return _executor.submit(prepare).result()


def _run(imagen_id):
    close_old_connections()
    try:
        from .tasks import procesar_imagen_cnn
        return procesar_imagen_cnn.run(imagen_id)
    except Exception:
        logger.exception("Falló la inferencia local en segundo plano para imagen %s", imagen_id)
        return None
    finally:
        close_old_connections()


def enqueue_local_inference(imagen_id):
    """Queue one image and return a stable id that polling can resolve via DB."""
    with _pending_lock:
        if imagen_id in _pending:
            return f"local-{imagen_id}"
        _pending.add(imagen_id)
    try:
        future = _executor.submit(_run, imagen_id)
    except Exception:
        _release(imagen_id)
        raise
    future.add_done_callback(lambda _: _release(imagen_id))
    return f"local-{imagen_id}"


def _release(imagen_id):
    with _pending_lock:
        _pending.discard(imagen_id)


def recover_pending_local_inferences():
    """Resume valid queued images after the development server restarts."""
    from estudios.models import ImagenDICOM
    image_ids = list(
        ImagenDICOM.objects.filter(
            estado_procesamiento="pendiente",
            apta_para_cnn=True,
            clasificacion_imagen="chest_xray",
        ).values_list("pk", flat=True).order_by("fecha_subida")
    )
    for image_id in image_ids:
        enqueue_local_inference(image_id)
    return len(image_ids)
