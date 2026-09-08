from django.db import models
from django.conf import settings
from pacientes.models import Estudio


class InformePreliminar(models.Model):
    ESTADO_CHOICES = [
        ("borrador", "Borrador"),
        ("revisado", "Revisado"),
        ("firmado", "Firmado"),
    ]
    estudio = models.OneToOneField(Estudio, on_delete=models.CASCADE, related_name="informe")
    medico = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"rol": "medico"},
        related_name="informes",
    )
    tecnica = models.TextField(default="Radiografía de Tórax PA. Técnica digital.")
    hallazgos = models.TextField(blank=True)
    impresion = models.TextField(blank=True)
    recomendaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="borrador")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_firmado = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Informe #{self.pk} — {self.estudio} [{self.estado}]"
