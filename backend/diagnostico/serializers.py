from rest_framework import serializers
from .models import ResultadoCNN
from .results import probabilities_es


class ResultadoCNNSerializer(serializers.ModelSerializer):
    patologias = serializers.SerializerMethodField()
    hallazgos = serializers.SerializerMethodField()
    advertencias_modelo = serializers.SerializerMethodField()

    def get_hallazgos(self, obj):
        return obj.patologias.get("hallazgos", [])

    def get_advertencias_modelo(self, obj):
        return obj.patologias.get("advertencias", [])

    def get_patologias(self, obj):
        return probabilities_es(obj.patologias)

    class Meta:
        model = ResultadoCNN
        fields = ("id", "imagen", "patologias", "hallazgos", "advertencias_modelo", "fecha_analisis", "tiempo_inferencia_seg")
        read_only_fields = fields
