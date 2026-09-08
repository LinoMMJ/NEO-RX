import os
import threading
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class DiagnosticoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'diagnostico'

    def ready(self):
        # Solo en el proceso principal (no en el reloader de manage.py runserver)
        if os.environ.get('RUN_MAIN') != 'true':
            return

        def _precargar():
            try:
                from diagnostico.services import DetectorTorax
                logger.info('[Neo RX] Precargando modelo CNN ResNet-50...')
                DetectorTorax.cargar()
                logger.info('[Neo RX] Modelo CNN listo.')
            except Exception as e:
                logger.warning(f'[Neo RX] No se pudo precargar el modelo: {e}')

        threading.Thread(target=_precargar, daemon=True).start()
