from rest_framework import serializers
from .models import ResultadoCNN
from .results import probabilities_es


class ResultadoCNNSerializer(serializers.ModelSerializer):
    patologias = serializers.SerializerMethodField()

    def get_patologias(self, obj):
        return probabilities_es(obj.patologias)

    class Meta:
        model = ResultadoCNN
        fields = "__all__"
        read_only_fields = ("id", "fecha_analisis", "tiempo_inferencia_seg", "patologias")
