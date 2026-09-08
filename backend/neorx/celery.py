import os
import logging
from celery import Celery
from celery.signals import worker_ready

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neorx.settings')

app = Celery('neorx')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

logger = logging.getLogger(__name__)


@worker_ready.connect
def precargar_modelo(**kwargs):
    """Precarga el modelo CNN cuando el Celery worker inicia, para que
    la primera tarea no tenga que esperar la descarga de pesos."""
    import time
    try:
        from diagnostico.services import DetectorTorax
        logger.info("[CELERY WORKER] Precargando modelo ResNet-50...")
        t0 = time.time()
        DetectorTorax.cargar()
        logger.info(f"[CELERY WORKER] Modelo listo en {time.time() - t0:.1f}s")
    except Exception as e:
        logger.error(f"[CELERY WORKER] Error al precargar modelo: {e}")
