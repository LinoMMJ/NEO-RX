"""
API endpoints para niveles clínicos centralizados.

Expone la configuración de umbrales y permite clasificar probabilidades
desde el frontend sin duplicar lógica.
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .niveles import get_api_response, clasificar_todas


class NivelesClinicosConfigView(APIView):
    """
    GET /api/diagnostico/niveles-clinicos/

    Retorna la configuración completa de umbrales para consumo del frontend.
    El frontend debe cachear esto y usarlo para clasificar TODAS las probabilidades.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_api_response())


class ClasificarProbabilidadesView(APIView):
    """
    POST /api/diagnostico/clasificar/

    Body: {"patologias": {"Neumonía": 0.75, "Derrame pleural": 0.30, ...}}
    Retorna: {"Neumonía": {nivel, color, umbral, descripcion, probabilidad}, ...}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patologias = request.data.get("patologias")
        if not patologias or not isinstance(patologias, dict):
            return Response(
                {"error": "Se requiere 'patologias' como objeto {nombre: probabilidad}"},
                status=400,
            )
        resultado = clasificar_todas(patologias)
        return Response(resultado)