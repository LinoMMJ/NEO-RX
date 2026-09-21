from django.db import models
from neorx.fields import EncryptedCIField
from neorx.encryption import ci_digest

ENCRYPTION_AVAILABLE = True


class PacienteQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "ci" in kwargs or "ci_search_hash" in kwargs:
            raise ValueError("Actualice CI mediante Paciente.save() para mantener el índice seguro.")
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        if kwargs.get("update_conflicts"):
            raise ValueError("Actualice identificadores mediante Paciente.save().")
        for obj in objs:
            obj.ci_search_hash = ci_digest(obj.ci)
        return super().bulk_create(objs, **kwargs)

    def bulk_update(self, objs, fields, **kwargs):
        if "ci" in fields or "ci_search_hash" in fields:
            raise ValueError("Actualice CI mediante Paciente.save().")
        return super().bulk_update(objs, fields, **kwargs)


class Paciente(models.Model):
    GENERO_CHOICES = [
        ("M", "Masculino"),
        ("F", "Femenino"),
        ("Otro", "Otro"),
    ]
    nombres = models.CharField(max_length=100)
    apellidos = models.CharField(max_length=100)
    # CI cifrado autenticado; el índice HMAC mantiene la unicidad normalizada.
    ci = EncryptedCIField(max_length=20)
    ci_search_hash = models.CharField(max_length=64, unique=True, editable=False)
    objects = PacienteQuerySet.as_manager()

    def save(self, *args, **kwargs):
        fields = kwargs.get("update_fields")
        if fields is None or "ci" in fields or "ci_search_hash" in fields:
            self.ci_search_hash = ci_digest(self.ci)
            if fields is not None:
                kwargs["update_fields"] = set(fields) | {"ci_search_hash"}
        return super().save(*args, **kwargs)
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
        ("requiere_repeticion", "Requiere repetición"),
    ]
    paciente = models.ForeignKey(Paciente, on_delete=models.CASCADE, related_name="estudios")
    fecha = models.DateField()
    tipo_estudio = models.CharField(max_length=200, default="Radiografía de Tórax PA")
    observaciones = models.TextField(blank=True)
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default="pendiente")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Estudio {self.tipo_estudio} — {self.paciente} ({self.fecha})"
