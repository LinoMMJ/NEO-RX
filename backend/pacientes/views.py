from django.db.models import Q
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import Paciente, Estudio
from .serializers import PacienteSerializer, EstudioSerializer


class PacienteViewSet(viewsets.ModelViewSet):
    serializer_class = PacienteSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Paciente.objects.all().order_by("-created_at")
        ci = self.request.query_params.get("ci")
        nombre = self.request.query_params.get("nombre")
        if ci:
            qs = qs.filter(ci__icontains=ci)
        if nombre:
            qs = qs.filter(Q(nombres__icontains=nombre) | Q(apellidos__icontains=nombre))
        return qs


class BuscarPacienteView(APIView):
    """GET /api/pacientes/buscar/?q=texto
    Busca por nombres, apellidos o CI (icontains). Hasta 10 resultados."""
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Estudio.objects.all().order_by("-created_at")
        paciente_id = self.request.query_params.get("paciente")
        if paciente_id:
            qs = qs.filter(paciente_id=paciente_id)
        return qs
