"""
Modelos transversales del proyecto Neo RX.
Incluye: AuditLog, AIModel, AIPrediction.
"""

import uuid
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings

User = get_user_model()


class AuditLog(models.Model):
    """Registro inmutable de auditoría para compliance médico."""

    ACTION_CHOICES = [
        ("create", "Crear"),
        ("read", "Leer"),
        ("update", "Actualizar"),
        ("delete", "Eliminar"),
        ("login", "Login"),
        ("logout", "Logout"),
        ("export", "Exportar"),
        ("firmar", "Firmar informe"),
        ("diagnostico", "Ejecutar diagnóstico"),
        ("gradcam", "Generar Grad-CAM"),
        ("process", "Procesar imagen"),
        ("validate", "Validar calidad de imagen"),
    ]

    id = models.BigAutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    request_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="audit_logs"
    )
    user_role = models.CharField(max_length=20, blank=True)

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)
    resource_type = models.CharField(max_length=50)  # 'paciente', 'estudio', 'informe', etc.
    resource_id = models.CharField(max_length=100, blank=True)

    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Detalles del cambio (JSON)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    # Metadatos adicionales
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} | {self.user} | {self.action} | {self.resource_type}#{self.resource_id}"


def get_client_ip(request):
    if request is None:
        return None
    x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded:
        return x_forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def redact_sensitive(value):
    if isinstance(value, dict):
        return {key: ("[REDACTED]" if str(key).lower() in {"ci", "filename"} or any(part in str(key).lower() for part in
                ("password", "token", "secret", "fernet", "authorization")) else redact_sensitive(item))
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item) for item in value]
    return value


def log_audit(
    request,
    action: str,
    resource_type: str,
    resource_id: str = "",
    before: dict = None,
    after: dict = None,
    metadata: dict = None,
):
    """Helper para registrar auditoría desde vistas/servicios."""
    try:
        AuditLog.objects.create(
            request_id=getattr(request, "request_id", uuid.uuid4()),
            user=request.user if hasattr(request, "user") and request.user.is_authenticated else None,
            user_role=getattr(request.user, "rol", "") if hasattr(request, "user") else "",
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
            before=redact_sensitive(before),
            after=redact_sensitive(after),
            metadata=redact_sensitive(metadata or {}),
        )
    except Exception:
        # Nunca fallar la request principal por auditoría
        pass


class AIModel(models.Model):
    """Modelo para versionado y gestión de modelos de IA."""

    name = models.CharField(max_length=100)
    version = models.CharField(max_length=50)
    architecture = models.CharField(max_length=100, default="resnet50")
    checkpoint_path = models.CharField(max_length=500)
    classes = models.JSONField(default=list)  # Lista de nombres de clases
    thresholds = models.JSONField(default=dict)  # Thresholds por clase (del checkpoint)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Metadatos de entrenamiento (compatibilidad migración 0001)
    dataset_name = models.CharField(max_length=100, blank=True)
    train_config = models.JSONField(default=dict, blank=True)
    metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} v{self.version} ({'activo' if self.is_active else 'inactivo'})"

    def save(self, *args, **kwargs):
        # Solo un modelo activo a la vez
        if self.is_active:
            AIModel.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class AIPrediction(models.Model):
    """Predicción de IA vinculada a un estudio y modelo específico."""

    estudio = models.ForeignKey(
        'pacientes.Estudio', on_delete=models.CASCADE, related_name="ai_predictions"
    )
    ai_model = models.ForeignKey(
        AIModel, on_delete=models.SET_NULL, null=True, blank=True, related_name="predictions"
    )

    # Resultados de la inferencia
    probabilities = models.JSONField(default=dict)  # {clase_en: probabilidad}
    thresholds = models.JSONField(default=dict)  # {clase_en: threshold}
    findings = models.JSONField(default=list)  # Lista de hallazgos detectados con metadata

    # Metadatos
    created_at = models.DateTimeField(auto_now_add=True)
    inference_time_ms = models.FloatField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["estudio", "created_at"]),
            models.Index(fields=["ai_model", "created_at"]),
        ]

    def __str__(self):
        return f"Predicción #{self.pk} — Estudio #{self.estudio_id} — Modelo {self.ai_model}"
