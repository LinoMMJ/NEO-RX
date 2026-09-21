from rest_framework import serializers
from .models import Paciente, Estudio


class PacienteSerializer(serializers.ModelSerializer):
    ci = serializers.CharField(max_length=20)

    def validate_ci(self, value):
        from neorx.encryption import ci_digest
        qs = Paciente.objects.filter(ci_search_hash=ci_digest(value))
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un paciente con este identificador.")
        return value

    class Meta:
        model = Paciente
        exclude = ("ci_search_hash",)
        read_only_fields = ("id", "created_at")


class EstudioSerializer(serializers.ModelSerializer):
    paciente_nombre = serializers.SerializerMethodField()
    informe_id = serializers.IntegerField(source="informe.id", read_only=True, default=None)
    informe_estado = serializers.CharField(source="informe.estado", read_only=True, default=None)
    ultima_imagen_id = serializers.IntegerField(read_only=True, allow_null=True)

    def get_paciente_nombre(self, obj):
        return f"{obj.paciente.nombres} {obj.paciente.apellidos}"

    def validate(self, attrs):
        request = self.context.get("request")
        if attrs.get("estado") == "requiere_repeticion" and request and request.user.rol != "recepcionista":
            raise serializers.ValidationError({"estado": "Solo recepción puede solicitar repetición técnica."})
        if attrs.get("estado") == "completado":
            raise serializers.ValidationError({"estado": "La finalización requiere firma médica del informe."})
        if self.instance and self.instance.estado == "completado":
            raise serializers.ValidationError("Un estudio con informe firmado no puede modificarse.")
        if self.instance and attrs.get("paciente", self.instance.paciente) != self.instance.paciente:
            raise serializers.ValidationError({"paciente": "No se puede reasignar el paciente de un estudio existente."})
        return attrs

    class Meta:
        model = Estudio
        fields = "__all__"
        read_only_fields = ("id", "created_at")
