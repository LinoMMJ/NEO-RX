from django.db import models
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pacientes.models import Estudio

class ImagenDICOM(models.Model):
    ESTADO_PROC_CHOICES = [
        ("pendiente", "Pendiente"),
        ("procesado", "Procesado"),
        ("sin_analisis", "Guardada sin analisis CNN"),
        ("error", "Error"),
    ]
    CLASIFICACION_CHOICES = [
        ("indeterminate", "Indeterminada"),
        ("chest_xray", "Radiografia de torax"),
        ("other_xray", "Otra radiografia"),
        ("not_xray", "No radiografica"),
    ]
    estudio = models.ForeignKey(Estudio, on_delete=models.CASCADE, related_name="imagenes")
    # Ruta interna; el binario no está cifrado. Se entrega mediante una vista autenticada.
    archivo_dicom = models.FileField(upload_to="dicom/%Y/%m/")
    archivo_png = models.FileField(upload_to="png/%Y/%m/", null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_nitida = models.BooleanField(null=True)
    varianza_laplaciana = models.FloatField(null=True)
    tipo_proyeccion = models.CharField(max_length=10, blank=True)       # PA | AP | LAT
    proyeccion_fuente = models.CharField(max_length=20, blank=True)     # dicom_tag | inferencia
    clasificacion_imagen = models.CharField(
        max_length=24, choices=CLASIFICACION_CHOICES, default="indeterminate"
    )
    region_anatomica = models.CharField(max_length=80, blank=True)
    es_radiografia = models.BooleanField(null=True)
    apta_para_cnn = models.BooleanField(default=False)
    confianza_clasificacion = models.FloatField(null=True, blank=True)
    fuente_clasificacion = models.CharField(max_length=32, blank=True)
    motivo_no_cnn = models.TextField(blank=True)
    estado_procesamiento = models.CharField(
        max_length=20, choices=ESTADO_PROC_CHOICES, default="pendiente"
    )

    def __str__(self):
        return f"DICOM #{self.pk} — Estudio #{self.estudio_id} ({self.estado_procesamiento})"
