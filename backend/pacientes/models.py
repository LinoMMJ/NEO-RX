from django.db import models


class Paciente(models.Model):
    GENERO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("Otro", "Otro"),
    ]
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    ci = models.CharField(max_length=20, unique=True)
    fecha_nacimiento = models.DateField()
    genero = models.CharField(max_length=10, choices=GENERO_CHOICES)
    telefono = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nombres} {self.apellidos} (CI: {self.ci})"


class Estudio(models.Model):
    ESTADO_CHOICES = [
        ("pendiente", "Pendiente"),
        ("en_proceso", "En Proceso"),
        ("completado", "Completado"),
    ]
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="estudios")
    fecha = models.DateField()
    tipo_estudio = models.CharField(max_length=200, default="Radiografía de Tórax PA")
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Estudio {self.tipo_estudio} — {self.paciente} ({self.fecha})"
