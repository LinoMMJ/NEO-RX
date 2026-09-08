from rest_framework import serializers
from .models import Paciente, Estudio


class PacienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Paciente
        fields = "__all__"
        read_only_fields = ("id", "created_at")


class EstudioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Estudio
        fields = "__all__"
        read_only_fields = ("id", "created_at")
