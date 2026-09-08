from rest_framework import serializers
from .models import ResultadoCNN


class ResultadoCNNSerializer(serializers.ModelSerializer):
    patologias = serializers.JSONField()

    class Meta:
        model = ResultadoCNN
        fields = "__all__"
        read_only_fields = ("id", "fecha_analisis", "tiempo_inferencia_seg", "patologias")
