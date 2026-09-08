from datetime import datetime
from io import BytesIO

from django.http import FileResponse
from django.template.loader import render_to_string
from rest_framework.views import APIView
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from pacientes.models import Estudio
from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from .models import InformePreliminar
from .serializers import InformePreliminarSerializer


# NOTA: las claves coinciden EXACTAMENTE con services.PATOLOGIAS_NEUMOLOGIA
# (sin acentos): "Neumonia", "Consolidacion", "Nodulo", "Neumotorax", etc.
# Usar acentos aquí provocaría .get() == 0 y el informe saldría siempre vacío.

def _pct(v):
    return f"{v * 100:.0f}%"


def generar_texto_hallazgos(resultado_cnn, tipo_proyeccion):
    """Genera texto clínico estructurado por regiones anatómicas.
    Umbral de mención: >15%. Umbral de hallazgo positivo: >45%."""
    patologias = resultado_cnn.patologias or {}
    tipo = tipo_proyeccion or "PA"
    texto = []

    # REGIÓN 1: PARÉNQUIMA PULMONAR
    pulmonares = {
        "Neumonia": patologias.get("Neumonia", 0),
        "Consolidacion": patologias.get("Consolidacion", 0),
        "Infiltrado": patologias.get("Infiltrado", 0),
        "Nodulo": patologias.get("Nodulo", 0),
        "Masa": patologias.get("Masa", 0),
        "Atelectasia": patologias.get("Atelectasia", 0),
        "Edema pulmonar": patologias.get("Edema pulmonar", 0),
        "Opacidad pulmonar": patologias.get("Opacidad pulmonar", 0),
    }
    hallazgos_pulmonares = {k: v for k, v in pulmonares.items() if v > 0.15}
    if hallazgos_pulmonares:
        positivos = [k for k, v in hallazgos_pulmonares.items() if v > 0.45]
        marginales = [k for k, v in hallazgos_pulmonares.items() if 0.15 < v <= 0.45]
        linea = "PARÉNQUIMA PULMONAR: "
        if positivos:
            linea += f"Se identifican opacidades compatibles con {', '.join(positivos).lower()}. "
        if marginales:
            probs = " / ".join(_pct(hallazgos_pulmonares[m]) for m in marginales)
            linea += (
                f"No se descartan hallazgos incipientes de {', '.join(marginales).lower()} "
                f"(probabilidad {probs}). "
            )
        texto.append(linea.strip())
    else:
        texto.append(
            "PARÉNQUIMA PULMONAR: Sin opacidades ni infiltrados significativos identificados."
        )

    # REGIÓN 2: ESPACIOS PLEURALES
    pleural = patologias.get("Derrame pleural", 0)
    engrosamiento = patologias.get("Engrosamiento pleural", 0)
    neum = patologias.get("Neumotorax", 0)
    pleura_hallazgos = []
    if pleural > 0.45:
        pleura_hallazgos.append(f"derrame pleural ({_pct(pleural)})")
    elif pleural > 0.15:
        pleura_hallazgos.append(f"probable derrame pleural ({_pct(pleural)})")
    if neum > 0.45:
        pleura_hallazgos.append(f"neumotórax ({_pct(neum)})")
    elif neum > 0.15:
        pleura_hallazgos.append(f"posible neumotórax ({_pct(neum)})")
    if engrosamiento > 0.30:
        pleura_hallazgos.append(f"engrosamiento pleural ({_pct(engrosamiento)})")
    if pleura_hallazgos:
        texto.append(f"ESPACIOS PLEURALES: Se observa {', '.join(pleura_hallazgos)}.")
    else:
        texto.append(
            "ESPACIOS PLEURALES: Ángulos costofrénicos libres. "
            "Sin evidencia de derrame ni neumotórax."
        )

    # REGIÓN 3: MEDIASTINO Y SILUETA CARDÍACA
    texto.append(
        "MEDIASTINO Y SILUETA CARDÍACA: Silueta cardíaca de tamaño conservado. "
        "Mediastino centrado de amplitud normal. Sin ensanchamiento mediastínico evidente."
    )

    # REGIÓN 4: ESTRUCTURAS ÓSEAS
    texto.append(
        "ESTRUCTURAS ÓSEAS: Arcos costales, clavículas y columna dorsal visibles "
        f"sin alteraciones morfológicas evidentes en la proyección {tipo}."
    )

    # REGIÓN 5: PARTES BLANDAS
    texto.append(
        "PARTES BLANDAS: Sin alteraciones significativas en tejidos blandos pericostales."
    )

    return "\n\n".join(texto)


def generar_impresion(resultado_cnn):
    """Resumen ejecutivo de los hallazgos."""
    patologias = resultado_cnn.patologias or {}
    top = sorted(patologias.items(), key=lambda x: x[1], reverse=True)
    criticos = [(k, v) for k, v in top if v > 0.65]
    moderados = [(k, v) for k, v in top if 0.40 < v <= 0.65]
    if not criticos and not moderados:
        return (
            "Radiografía de tórax sin hallazgos patológicos significativos "
            "según el análisis asistido por red neuronal convolucional ResNet-50. "
            "Se sugiere correlación clínica."
        )
    lineas = []
    if criticos:
        hallazgos_str = ", ".join(f"{k} ({_pct(v)})" for k, v in criticos)
        lineas.append(f"Hallazgos de alta probabilidad compatibles con: {hallazgos_str}.")
    if moderados:
        hallazgos_str = ", ".join(f"{k} ({_pct(v)})" for k, v in moderados)
        lineas.append(f"Hallazgos de probabilidad moderada a considerar: {hallazgos_str}.")
    lineas.append(
        "Impresión generada por sistema de apoyo diagnóstico (CNN ResNet-50). "
        "Requiere validación y firma del médico radiólogo especialista."
    )
    return " ".join(lineas)


def generar_recomendaciones(resultado_cnn):
    patologias = resultado_cnn.patologias or {}
    if not patologias:
        return "Control según criterio clínico. Sin hallazgos que requieran seguimiento urgente."
    top_proba = max(patologias.values())
    top_nombre = max(patologias, key=patologias.get)
    if top_proba > 0.65:
        return (
            f"Correlación clínica urgente recomendada. "
            f"Hallazgo principal ({top_nombre}) con alta probabilidad ({_pct(top_proba)}). "
            f"Considerar seguimiento con tomografía computada de tórax según criterio clínico."
        )
    elif top_proba > 0.40:
        return (
            "Correlación clínica recomendada. "
            "Seguimiento radiológico en 4-6 semanas si persiste sintomatología."
        )
    return "Control según criterio clínico. Sin hallazgos que requieran seguimiento urgente."


class GenerarInformeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        estudio_id = request.data.get("estudio_id")
        if not estudio_id:
            return Response({"error": "Se requiere 'estudio_id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            estudio = Estudio.objects.get(pk=estudio_id)
        except Estudio.DoesNotExist:
            return Response({"error": "Estudio no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # Imagen más reciente del estudio
        imagen = ImagenDICOM.objects.filter(estudio=estudio).order_by("-fecha_subida").first()
        if imagen is None:
            return Response(
                {"error": "El estudio no tiene imágenes asociadas."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            resultado = ResultadoCNN.objects.get(imagen=imagen)
        except ResultadoCNN.DoesNotExist:
            return Response(
                {"error": "No existe resultado CNN para este estudio."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        tipo_proyeccion = imagen.tipo_proyeccion or "PA"
        calidad = "adecuada" if imagen.es_nitida else "limitada por borrosidad"

        informe, _ = InformePreliminar.objects.get_or_create(estudio=estudio)
        informe.tecnica = (
            f"Radiografía de Tórax {tipo_proyeccion}. Técnica digital con detector "
            f"de panel plano. Calidad técnica {calidad}."
        )
        informe.hallazgos = generar_texto_hallazgos(resultado, tipo_proyeccion)
        informe.impresion = generar_impresion(resultado)
        informe.recomendaciones = generar_recomendaciones(resultado)
        if getattr(request.user, "rol", None) == "medico" and informe.medico is None:
            informe.medico = request.user
        informe.save()

        serializer = InformePreliminarSerializer(informe, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class InformePreliminarDetailView(RetrieveUpdateAPIView):
    queryset = InformePreliminar.objects.all()
    serializer_class = InformePreliminarSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_update(self, serializer):
        from django.utils import timezone
        nuevo_estado = self.request.data.get("estado")
        extra = {}
        # Al firmar, sellar la fecha y asignar médico firmante
        if nuevo_estado == "firmado":
            extra["fecha_firmado"] = timezone.now()
            if getattr(self.request.user, "rol", None) == "medico":
                extra["medico"] = self.request.user
        serializer.save(**extra)


class DescargarInformePDFView(APIView):
    """GET /api/informes/<pk>/descargar/ — genera y descarga el informe como PDF."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            from xhtml2pdf import pisa
        except ImportError:
            return Response(
                {"error": "xhtml2pdf no instalado. Ejecuta: pip install xhtml2pdf"},
                status=status.HTTP_501_NOT_IMPLEMENTED,
            )

        try:
            informe = InformePreliminar.objects.select_related(
                "estudio__paciente", "medico"
            ).get(pk=pk)
        except InformePreliminar.DoesNotExist:
            return Response({"error": "Informe no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        if informe.estado != "firmado":
            return Response(
                {"error": "Solo se pueden descargar informes firmados."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        paciente = informe.estudio.paciente
        hoy = datetime.today().date()
        edad = (
            hoy.year - paciente.fecha_nacimiento.year
            - ((hoy.month, hoy.day) < (paciente.fecha_nacimiento.month, paciente.fecha_nacimiento.day))
        )

        contexto = {
            "informe": informe,
            "estudio": informe.estudio,
            "paciente": paciente,
            "medico": informe.medico,
            "edad": edad,
            "fecha_hoy": hoy.strftime("%d/%m/%Y"),
        }
        try:
            html_string = render_to_string("informes/informe_pdf.html", contexto)
            pdf_bytes = BytesIO()
            result = pisa.CreatePDF(html_string, dest=pdf_bytes)
            if result.err:
                return Response(
                    {"error": f"Error al renderizar el PDF ({result.err} errores de formato)."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )
        except Exception as exc:
            return Response(
                {"error": f"Error al generar el PDF: {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        pdf_bytes.seek(0)

        filename = f"Informe_{paciente.ci}_{informe.estudio.id}.pdf"
        response = FileResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
