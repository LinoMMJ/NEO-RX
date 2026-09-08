import numpy as np
import pydicom
from PIL import Image as PILImage

from rest_framework.generics import RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from estudios.models import ImagenDICOM
from .models import ResultadoCNN
from .serializers import ResultadoCNNSerializer
from .services import DetectorTorax, PATOLOGIAS_NEUMOLOGIA


class ResultadoCNNView(RetrieveAPIView):
    serializer_class = ResultadoCNNSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        imagen_id = self.kwargs["imagen_id"]
        return ResultadoCNN.objects.select_related("imagen").get(imagen_id=imagen_id)

    def retrieve(self, request, *args, **kwargs):
        imagen_id = self.kwargs["imagen_id"]
        try:
            instance = self.get_object()
        except ResultadoCNN.DoesNotExist:
            try:
                img = ImagenDICOM.objects.get(pk=imagen_id)
                return Response(
                    {"estado_procesamiento": img.estado_procesamiento},
                    status=status.HTTP_200_OK,
                )
            except ImagenDICOM.DoesNotExist:
                return Response({"estado_procesamiento": "pendiente"}, status=status.HTTP_200_OK)

        imagen = instance.imagen
        from estudios.views import _get_imagen_url
        data = self.get_serializer(instance).data
        data["imagen_id"] = imagen.pk
        data["estado_procesamiento"] = imagen.estado_procesamiento
        data["es_nitida"] = imagen.es_nitida
        data["varianza_laplaciana"] = imagen.varianza_laplaciana
        url = _get_imagen_url(request, imagen)
        if url:
            data["imagen_png_url"] = url
        if imagen.tipo_proyeccion:
            data["proyeccion"] = {
                "tipo": imagen.tipo_proyeccion,
                "fuente": imagen.proyeccion_fuente,
            }
        return Response(data)


class GradCAMView(APIView):
    """
    GET /api/diagnostico/gradcam/?imagen_id=X&pathology=Pneumonia

    Genera el mapa de calor Grad-CAM para la imagen y la patología indicadas.
    Si no se pasa pathology, usa la de mayor probabilidad en ResultadoCNN.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        imagen_id = request.query_params.get("imagen_id")
        pathology_en = request.query_params.get("pathology")  # nombre en inglés (e.g. "Pneumonia")

        if not imagen_id:
            return Response({"error": "Se requiere 'imagen_id'."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            imagen = ImagenDICOM.objects.select_related("resultado_cnn").get(pk=imagen_id)
        except ImagenDICOM.DoesNotExist:
            return Response({"error": "Imagen no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        try:
            resultado = getattr(imagen, "resultado_cnn", None)

            # Si no se especificó patología, usar la de mayor probabilidad
            if not pathology_en:
                if resultado and resultado.patologias:
                    top_es = next(iter(resultado.patologias))
                    # Invertir el mapa español → inglés
                    pathology_en = next(
                        (k for k, v in PATOLOGIAS_NEUMOLOGIA.items() if v == top_es), None
                    )
                if not pathology_en:
                    return Response(
                        {"error": "No se encontró patología de referencia."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            modelo = DetectorTorax.cargar()

            if pathology_en not in list(modelo.pathologies):
                return Response(
                    {"error": f"Patología '{pathology_en}' no reconocida por el modelo."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            indice_clase = list(modelo.pathologies).index(pathology_en)

            # Leer datos de la imagen
            ruta = imagen.archivo_dicom.path
            ruta_lower = ruta.lower()

            if ruta_lower.endswith(".dcm") or ruta_lower.endswith(".dicom"):
                ds = pydicom.dcmread(ruta)
                arr = ds.pixel_array.astype(np.float32)
                if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
                    arr = arr.max() - arr
                if arr.ndim > 2:
                    arr = arr[:, :, 0]
                bits = getattr(ds, "BitsStored", 12)
                maxval = float(2 ** bits - 1)
            else:
                arr = np.array(PILImage.open(ruta).convert("L")).astype(np.float32)
                maxval = 255.0

            tensor = DetectorTorax._preprocesar(arr, maxval)

            from .gradcam import GeneradorGradCAM
            # Calcular cam UNA VEZ y reutilizar en ambos overlays
            cam = GeneradorGradCAM.calcular(modelo, tensor, indice_clase)
            centroide = GeneradorGradCAM.get_centroide(cam)
            overlay = GeneradorGradCAM.overlay_base64(modelo, tensor, indice_clase, arr, cam=cam)
            solo_calor = GeneradorGradCAM.overlay_solo_heatmap_base64(
                modelo, tensor, indice_clase, cam=cam
            )

            return Response({
                "overlay": overlay,
                "solo_calor": solo_calor,
                "patologia": pathology_en,
                "activacion_maxima": round(float(cam.max()), 4),
                "centroide": centroide,
            })

        except Exception as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
