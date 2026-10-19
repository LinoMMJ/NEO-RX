from rest_framework import serializers
from .models import ImagenDICOM


class ImagenDICOMSerializer(serializers.ModelSerializer):
    es_nitida = serializers.BooleanField(read_only=True)

    class Meta:
        model = ImagenDICOM
        fields = (
            "id", "estudio", "archivo_dicom", "archivo_png", "fecha_subida",
            "es_nitida", "varianza_laplaciana", "tipo_proyeccion",
            "proyeccion_fuente", "clasificacion_imagen", "region_anatomica",
            "es_radiografia", "apta_para_cnn", "confianza_clasificacion",
            "fuente_clasificacion", "motivo_no_cnn", "estado_procesamiento",
        )
        read_only_fields = fields
