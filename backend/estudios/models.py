from django.db import models
from pacientes.models import Estudio


class ImagenDICOM(models.Model):
    ESTADO_PROC_CHOICES = [
        ("pendiente", "Pendiente"),
        ("procesado", "Procesado"),
        ("error", "Error"),
    ]
    estudio = models.ForeignKey(Estudio, on_delete=models.CASCADE, related_name="imagenes")
    archivo_dicom = models.FileField(upload_to="dicom/%Y/%m/")
    archivo_png = models.FileField(upload_to="png/%Y/%m/", null=True, blank=True)
    fecha_subida = models.DateTimeField(auto_now_add=True)
    es_nitida = models.BooleanField(null=True)
    varianza_laplaciana = models.FloatField(null=True)
    tipo_proyeccion = models.CharField(max_length=10, blank=True)       # PA | AP | LAT
    proyeccion_fuente = models.CharField(max_length=20, blank=True)     # dicom_tag | inferencia
    estado_procesamiento = models.CharField(
        max_length=20, choices=ESTADO_PROC_CHOICES, default="pendiente"
    )

    def __str__(self):
        return f"DICOM #{self.pk} — Estudio #{self.estudio_id} ({self.estado_procesamiento})"
