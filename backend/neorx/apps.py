import os
import logging
import time
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class NeorxConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'neorx'
    verbose_name = 'Neo RX'

    def ready(self):
        import sys
        # Solo cuando se lanza el servidor web (no en migrate/shell/etc.)
        if 'runserver' not in sys.argv:
            return
        # En el dev server, ready() se llama dos veces (watcher + serving process).
        # Solo precargar en el proceso que sirve requests (RUN_MAIN=true).
        if os.environ.get('RUN_MAIN') != 'true':
            return
        try:
            from diagnostico.services import DetectorTorax
            logger.info("[STARTUP] Precargando modelo ResNet-50...")
            t0 = time.time()
            detector = DetectorTorax.cargar()
            logger.info(
                f"[STARTUP] Modelo listo en {time.time() - t0:.1f}s "
                f"({len(detector.pathologies)} patologías)"
            )
        except Exception as e:
            logger.error(f"[STARTUP] Error al precargar modelo: {e}")
            logger.warning("[STARTUP] La primera inferencia será más lenta.")
