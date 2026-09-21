from rest_framework import serializers
from estudios.models import ImagenDICOM
from .models import InformePreliminar
from rest_framework.exceptions import ValidationError
from diagnostico.results import probabilities_es


class InformePreliminarSerializer(serializers.ModelSerializer):
    # Datos derivados de solo lectura para el encabezado del informe
    paciente = serializers.SerializerMethodField()
    proyeccion = serializers.SerializerMethodField()
    probabilidades = serializers.SerializerMethodField()
    imagen_png_url = serializers.SerializerMethodField()
    medico_nombre = serializers.SerializerMethodField()
    estudio_fecha = serializers.SerializerMethodField()

    class Meta:
        model = InformePreliminar
        fields = "__all__"
        read_only_fields = ("id", "estudio", "medico", "fecha_creacion", "fecha_firmado")

    def validate(self, attrs):
        if self.instance and self.instance.estado == "firmado":
            raise ValidationError("Un informe firmado no puede modificarse.")
        state = attrs.get("estado")
        if state == "firmado" and self.instance and self.instance.estado != "revisado":
            raise ValidationError("El informe debe estar revisado antes de firmarse.")
        return attrs

    def _imagen(self, obj):
        return (
            ImagenDICOM.objects.filter(estudio=obj.estudio)
            .order_by("-fecha_subida")
            .first()
        )

    def get_paciente(self, obj):
        p = obj.estudio.paciente
        return {
            "id": p.id,
            "nombres": p.nombres,
            "apellidos": p.apellidos,
            "ci": p.ci,
            "fecha_nacimiento": p.fecha_nacimiento,
            "genero": p.genero,
        }

    def get_estudio_fecha(self, obj):
        return obj.estudio.fecha

    def get_proyeccion(self, obj):
        img = self._imagen(obj)
        if img and img.tipo_proyeccion:
            return {"tipo": img.tipo_proyeccion, "fuente": img.proyeccion_fuente}
        return {"tipo": "PA", "fuente": ""}

    def get_probabilidades(self, obj):
        img = self._imagen(obj)
        resultado = getattr(img, "resultado_cnn", None) if img else None
        return probabilities_es(resultado.patologias) if resultado else {}

    def get_imagen_png_url(self, obj):
        img = self._imagen(obj)
        if img and img.archivo_png:
            request = self.context.get("request")
            url = img.archivo_png.url
            return request.build_absolute_uri(url) if request else url
        return None

    def get_medico_nombre(self, obj):
        if obj.medico:
            return obj.medico.get_full_name() or obj.medico.username
        return None
