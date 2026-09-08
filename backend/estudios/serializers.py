from rest_framework import serializers
from .models import ImagenDICOM


class ImagenDICOMSerializer(serializers.ModelSerializer):
    es_nitida = serializers.BooleanField(read_only=True)

    class Meta:
        model = ImagenDICOM
        fields = "__all__"
        read_only_fields = ("id", "fecha_subida", "es_nitida", "varianza_laplaciana", "estado_procesamiento")
