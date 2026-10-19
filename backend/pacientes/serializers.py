from rest_framework import serializers
from .models import Paciente, Estudio
from neorx.validation import clean_plain_text


class PacienteSerializer(serializers.ModelSerializer):
    ci = serializers.CharField(max_length=20)

    def validate_ci(self, value):
        value = clean_plain_text(value, max_length=20, field_name="identificador")
        from neorx.encryption import ci_digest
        qs = Paciente.objects.filter(ci_search_hash=ci_digest(value))
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya existe un paciente con este identificador.")
        return value

    def validate_nombres(self, value):
        return clean_plain_text(value, max_length=100, field_name="nombres")

    def validate_apellidos(self, value):
        return clean_plain_text(value, max_length=100, field_name="apellidos")

    def validate_telefono(self, value):
        return clean_plain_text(value, max_length=20, field_name="teléfono")

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

    def validate_tipo_estudio(self, value):
        return clean_plain_text(value, max_length=200, field_name="tipo de estudio")

    def validate_observaciones(self, value):
        return clean_plain_text(
            value, max_length=5000, field_name="observaciones", allow_newlines=True
        )

    class Meta:
        model = Estudio
        fields = (
            "id", "paciente", "paciente_nombre", "fecha", "tipo_estudio",
            "observaciones", "estado", "created_at", "informe_id",
            "informe_estado", "ultima_imagen_id",
        )
        read_only_fields = (
            "id", "created_at", "paciente_nombre", "informe_id",
            "informe_estado", "ultima_imagen_id",
        )
