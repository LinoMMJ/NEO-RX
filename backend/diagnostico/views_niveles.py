"""
API endpoints para niveles clínicos centralizados (visualización).

Expone la configuración de umbrales VISUALES para el frontend.
Los thresholds de DECISIÓN del modelo provienen del checkpoint y se aplican en DetectorTorax.
"""

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .niveles import get_api_response, clasificar_todas_para_visualizacion


class NivelesClinicosConfigView(APIView):
    """
    GET /api/diagnostico/niveles-clinicos/

    Retorna la configuración completa de umbrales VISUALES para consumo del frontend.
    El frontend debe cachear esto y usarlo para clasificar TODAS las probabilidades
    con fines de CODIFICACIÓN DE COLOR (Alto/Moderado/Leve/Marginal).

    NOTA: Los thresholds de DECISIÓN (detección sí/no) provienen del checkpoint
    y se aplican en DetectorTorax.predecir(). Este endpoint solo provee visualización.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(get_api_response())


class ClasificarProbabilidadesView(APIView):
    """
    POST /api/diagnostico/clasificar/

    Body: {"patologias": {"Neumonía": 0.75, "Derrame pleural": 0.30, ...}}
    Retorna: {"Neumonía": {nivel, color, umbral_visual, descripcion, probabilidad,
                            detectado_por_modelo, threshold_modelo}, ...}
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        patologias = request.data.get("patologias")
        if not patologias or not isinstance(patologias, dict):
            return Response(
                {"error": "Se requiere 'patologias' como objeto {nombre_es: probabilidad}"},
                status=400,
            )

        # Opcional: thresholds del modelo para incluir info de detección
        thresholds_modelo = request.data.get("thresholds_modelo")
        detectados = request.data.get("detectados")

        resultado = clasificar_todas_para_visualizacion(
            patologias,
            thresholds_modelo=thresholds_modelo,
            detectados=detectados
        )
        return Response(resultado)
