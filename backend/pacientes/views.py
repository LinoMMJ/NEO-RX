from django.db.models import Q, OuterRef, Subquery
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Paciente, Estudio
from .filters import PatientOrderingFilter
from .serializers import PacienteSerializer, EstudioSerializer
from neorx.models import log_audit
from neorx.permissions import ClinicalRecordPermission


class StandardResultsPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class PacienteViewSet(viewsets.ModelViewSet):
    serializer_class = PacienteSerializer
    permission_classes = [ClinicalRecordPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, PatientOrderingFilter]
    filterset_fields = ['genero']
    search_fields = ['nombres', 'apellidos', 'ci']
    ordering_fields = ['nombres', 'apellidos', 'ci', 'created_at', 'fecha_nacimiento']
    ordering = ['-created_at']

    def get_queryset(self):
        qs = Paciente.objects.all().order_by("-created_at")
        ci = self.request.query_params.get("ci")
        nombre = self.request.query_params.get("nombre")
        genero = self.request.query_params.get("genero")
        fecha_desde = self.request.query_params.get("fecha_desde")
        fecha_hasta = self.request.query_params.get("fecha_hasta")
        from neorx.views_workspace import date_filters
        date_filters(self.request.query_params)

        if ci:
            qs = qs.filter(ci__icontains=ci)
        if nombre:
            qs = qs.filter(Q(nombres__icontains=nombre) | Q(apellidos__icontains=nombre))
        if genero:
            qs = qs.filter(genero=genero)
        if fecha_desde:
            qs = qs.filter(created_at__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(created_at__date__lte=fecha_hasta)
        return qs

    def perform_destroy(self, instance):
        if instance.estudios.filter(informe__estado="firmado").exists():
            raise ValidationError("No se puede eliminar un paciente con informes firmados.")
        pk = instance.pk
        instance.delete()
        log_audit(self.request, action="delete", resource_type="paciente", resource_id=str(pk))

    def perform_create(self, serializer):
        paciente = serializer.save()
        log_audit(
            self.request,
            action="create",
            resource_type="paciente",
            resource_id=str(paciente.pk),
            after={
                "nombres": paciente.nombres,
                "apellidos": paciente.apellidos,
                "ci": paciente.ci,
                "fecha_nacimiento": str(paciente.fecha_nacimiento),
                "genero": paciente.genero,
            },
            metadata={"created_by": self.request.user.username if self.request.user.is_authenticated else "system"},
        )
        return paciente

    def perform_update(self, serializer):
        # Capturar estado antes
        paciente_antes = self.get_object()
        before = {
            "nombres": paciente_antes.nombres,
            "apellidos": paciente_antes.apellidos,
            "ci": paciente_antes.ci,
            "fecha_nacimiento": str(paciente_antes.fecha_nacimiento),
            "genero": paciente_antes.genero,
        }
        paciente = serializer.save()
        after = {
            "nombres": paciente.nombres,
            "apellidos": paciente.apellidos,
            "ci": paciente.ci,
            "fecha_nacimiento": str(paciente.fecha_nacimiento),
            "genero": paciente.genero,
        }
        log_audit(
            self.request,
            action="update",
            resource_type="paciente",
            resource_id=str(paciente.pk),
            before=before,
            after=after,
            metadata={"updated_by": self.request.user.username if self.request.user.is_authenticated else "system"},
        )
        return paciente


class BuscarPacienteView(APIView):
    """GET /api/pacientes/buscar/?q=texto
    Busca por nombres, apellidos o CI (icontains). Hasta 10 resultados."""
    permission_classes = [ClinicalRecordPermission]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response([])
        qs = Paciente.objects.filter(
            Q(nombres__icontains=q) | Q(apellidos__icontains=q) | Q(ci__icontains=q)
        ).order_by("apellidos", "nombres")[:10]
        data = [
            {
                "id": p.id,
                "nombres": p.nombres,
                "apellidos": p.apellidos,
                "ci": p.ci,
                "fecha_nacimiento": p.fecha_nacimiento,
                "genero": p.genero,
            }
            for p in qs
        ]
        return Response(data)


class EstudioViewSet(viewsets.ModelViewSet):
    serializer_class = EstudioSerializer
    permission_classes = [ClinicalRecordPermission]
    pagination_class = StandardResultsPagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['estado', 'paciente']
    search_fields = ['tipo_estudio', 'observaciones', 'paciente__nombres', 'paciente__apellidos', 'paciente__ci']
    ordering_fields = ['fecha', 'created_at', 'estado']
    ordering = ['-created_at']

    def get_queryset(self):
        from estudios.models import ImagenDICOM
        latest = ImagenDICOM.objects.filter(estudio_id=OuterRef('pk')).order_by('-fecha_subida', '-pk').values('pk')[:1]
        qs = Estudio.objects.select_related('paciente', 'informe').annotate(ultima_imagen_id=Subquery(latest)).order_by("-created_at")
        paciente_id = self.request.query_params.get("paciente")
        estado = self.request.query_params.get("estado")
        fecha_desde = self.request.query_params.get("fecha_desde")
        fecha_hasta = self.request.query_params.get("fecha_hasta")
        from neorx.views_workspace import date_filters
        date_filters(self.request.query_params)
        tipo_estudio = self.request.query_params.get("tipo_estudio")

        if paciente_id:
            try:
                paciente_id = int(paciente_id)
                if paciente_id < 1:
                    raise ValueError
            except (ValueError, TypeError):
                raise ValidationError({"paciente": "Seleccione un paciente válido."})
            qs = qs.filter(paciente_id=paciente_id)
        if estado:
            qs = qs.filter(estado=estado)
        if fecha_desde:
            qs = qs.filter(created_at__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(created_at__date__lte=fecha_hasta)
        if tipo_estudio:
            qs = qs.filter(tipo_estudio__icontains=tipo_estudio)
        queue = self.request.query_params.get("cola")
        if queue == "informes":
            qs = qs.exclude(informe__estado="firmado").exclude(estado="requiere_repeticion")
        elif queue == "procesamiento":
            qs = qs.filter(imagenes__estado_procesamiento="pendiente").distinct()
        elif queue == "errores":
            qs = qs.filter(imagenes__estado_procesamiento="error").distinct()
        elif queue == "repeticion":
            qs = qs.filter(estado="requiere_repeticion")
        elif queue:
            raise ValidationError({"cola": "Cola desconocida."})
        return qs

    def perform_destroy(self, instance):
        if hasattr(instance, "informe") and instance.informe.estado == "firmado":
            raise ValidationError("No se puede eliminar un estudio con informe firmado.")
        pk = instance.pk
        instance.delete()
        log_audit(self.request, action="delete", resource_type="estudio", resource_id=str(pk))

    def perform_create(self, serializer):
        estudio = serializer.save()
        log_audit(
            self.request,
            action="create",
            resource_type="estudio",
            resource_id=str(estudio.pk),
            after={
                "fecha": str(estudio.fecha),
                "tipo_estudio": estudio.tipo_estudio,
                "paciente_id": estudio.paciente_id,
                "estado": estudio.estado,
            },
            metadata={"created_by": self.request.user.username if self.request.user.is_authenticated else "system"},
        )
        return estudio

    def perform_update(self, serializer):
        estudio_antes = self.get_object()
        before = {
            "fecha": str(estudio_antes.fecha),
            "tipo_estudio": estudio_antes.tipo_estudio,
            "estado": estudio_antes.estado,
        }
        estudio = serializer.save()
        after = {
            "fecha": str(estudio.fecha),
            "tipo_estudio": estudio.tipo_estudio,
            "estado": estudio.estado,
        }
        log_audit(
            self.request,
            action="update",
            resource_type="estudio",
            resource_id=str(estudio.pk),
            before={"fecha": str(estudio_antes.fecha), "tipo_estudio": estudio_antes.tipo_estudio, "estado": estudio_antes.estado},
            after=after,
            metadata={"updated_by": self.request.user.username if self.request.user.is_authenticated else "system"},
        )
        return estudio
