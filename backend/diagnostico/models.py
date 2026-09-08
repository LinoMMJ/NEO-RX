from django.db import models
from estudios.models import ImagenDICOM


class ResultadoCNN(models.Model):
    imagen = models.OneToOneField(ImagenDICOM, on_delete=models.CASCADE, related_name="resultado_cnn")
    patologias = models.JSONField()
    fecha_analisis = models.DateTimeField(auto_now_add=True)
    tiempo_inferencia_seg = models.FloatField(null=True)

    def __str__(self):
        return f"ResultadoCNN para ImagenDICOM #{self.imagen_id}"
