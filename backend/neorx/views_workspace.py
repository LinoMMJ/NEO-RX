"""Operational workspace: aggregate counts and a privacy-limited activity feed."""
from datetime import date
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from pacientes.models import Paciente, Estudio
from pacientes.views import StandardResultsPagination
from .models import AuditLog
from .permissions import ClinicalRecordPermission


def date_filters(params):
    dates = {}
    for key in ("fecha_desde", "fecha_hasta"):
        if params.get(key):
            try:
                dates[key] = date.fromisoformat(params[key])
            except (TypeError, ValueError):
                raise ValidationError({key: "Utilice una fecha válida AAAA-MM-DD."})
    if dates.get("fecha_desde") and dates.get("fecha_hasta") and dates["fecha_desde"] > dates["fecha_hasta"]:
        raise ValidationError({"fecha_hasta": "Debe ser posterior o igual a la fecha inicial."})
    return dates


def filter_dates(qs, params, field):
    dates = date_filters(params)
    if "fecha_desde" in dates:
        qs = qs.filter(**{field + "__gte": dates["fecha_desde"]})
    if "fecha_hasta" in dates:
        qs = qs.filter(**{field + "__lte": dates["fecha_hasta"]})
    return qs


class WorkspaceSummaryView(APIView):
    permission_classes = [ClinicalRecordPermission]

    def get(self, request):
        studies = filter_dates(Estudio.objects.all(), request.query_params, "created_at__date")
        data = {
            "pacientes_total": Paciente.objects.count(),
            "estudios_total": studies.count(),
            "estudios_por_estado": list(studies.values("estado").annotate(total=Count("id")).order_by("estado")),
            "informes_pendientes": studies.exclude(informe__estado="firmado").exclude(estado="requiere_repeticion").count(),
            "procesamiento_pendiente": studies.filter(imagenes__estado_procesamiento="pendiente").distinct().count(),
            "errores_procesamiento": studies.filter(imagenes__estado_procesamiento="error").distinct().count(),
            "repeticiones": studies.filter(estado="requiere_repeticion").count(),
            "estudios_por_dia": list(studies.values("created_at__date").annotate(total=Count("id")).order_by("created_at__date")),
        }
        if request.user.rol == "administrador":
            users = get_user_model().objects.all()
            data["administracion"] = {
                "usuarios_total": users.count(), "usuarios_activos": users.filter(is_active=True).count(),
                "usuarios_por_rol": list(users.values("rol").annotate(total=Count("id")).order_by("rol")),
                "movimientos_total": filter_dates(AuditLog.objects.all(), request.query_params, "timestamp__date").count(),
            }
        return Response(data)


class ActivitySerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()

    def get_actor(self, obj):
        return obj.user.username if obj.user else "Sistema / cuenta eliminada"

    class Meta:
        model = AuditLog
        fields = ("id", "timestamp", "actor", "user_role", "action", "resource_type", "resource_id")
        read_only_fields = fields


class ActivityListView(ListAPIView):
    permission_classes = [ClinicalRecordPermission]
    serializer_class = ActivitySerializer
    pagination_class = StandardResultsPagination

    def get_queryset(self):
        qs = AuditLog.objects.select_related("user").order_by("-timestamp", "-id")
        if self.request.user.rol != "administrador":
            qs = qs.filter(user=self.request.user)
        params = self.request.query_params
        qs = filter_dates(qs, params, "timestamp__date")
        for field in ("action", "resource_type"):
            if params.get(field):
                qs = qs.filter(**{field: params[field]})
        if params.get("search"):
            term = params["search"][:100]
            qs = qs.filter(Q(user__username__icontains=term) | Q(resource_type__icontains=term) | Q(resource_id__icontains=term))
        return qs
