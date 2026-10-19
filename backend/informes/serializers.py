from rest_framework import serializers
from estudios.models import ImagenDICOM
from .models import InformePreliminar
from rest_framework.exceptions import ValidationError
from diagnostico.results import probabilities_es, threshold_findings
from neorx.validation import clean_plain_text
import re


class InformePreliminarSerializer(serializers.ModelSerializer):
    # Datos derivados de solo lectura para el encabezado del informe
    paciente = serializers.SerializerMethodField()
    proyeccion = serializers.SerializerMethodField()
    probabilidades = serializers.SerializerMethodField()
    hallazgos_ia = serializers.SerializerMethodField()
    imagen_png_url = serializers.SerializerMethodField()
    medico_nombre = serializers.SerializerMethodField()
    estudio_fecha = serializers.SerializerMethodField()

    class Meta:
        model = InformePreliminar
        fields = (
            "id", "estudio", "medico", "tecnica", "hallazgos",
            "correlacion_clinica", "impresion", "recomendaciones", "estado",
            "fecha_creacion", "fecha_firmado", "paciente", "proyeccion",
            "probabilidades", "hallazgos_ia", "imagen_png_url", "medico_nombre", "estudio_fecha", "imagen_origen",
        )
        read_only_fields = (
            "id", "estudio", "medico", "fecha_creacion", "fecha_firmado",
            "paciente", "proyeccion", "probabilidades", "imagen_png_url",
            "medico_nombre", "estudio_fecha", "imagen_origen",
        )

    def validate(self, attrs):
        for field in ("tecnica", "hallazgos", "correlacion_clinica", "impresion", "recomendaciones"):
            if field in attrs:
                attrs[field] = clean_plain_text(
                    attrs[field], max_length=20000, field_name=field.replace("_", " "),
                    allow_newlines=True,
                )
        if self.instance and self.instance.estado == "firmado":
            raise ValidationError("Un informe firmado no puede modificarse.")
        state = attrs.get("estado")
        if state == "firmado" and self.instance and self.instance.estado != "revisado":
            raise ValidationError("El informe debe estar revisado antes de firmarse.")
        if state == "firmado":
            required = ("tecnica", "hallazgos", "correlacion_clinica", "impresion", "recomendaciones")
            missing = []
            for field in required:
                value = attrs.get(field, getattr(self.instance, field, ""))
                if not str(value or "").strip():
                    missing.append(field)
                elif re.search(r"\[(describir|valorar|completar)[^\]]*\]", str(value), re.I):
                    missing.append(field)
            if missing:
                labels = {
                    "tecnica": "técnica",
                    "hallazgos": "hallazgos",
                    "correlacion_clinica": "correlación clínico-radiológica",
                    "impresion": "impresión diagnóstica",
                    "recomendaciones": "recomendaciones",
                }
                raise ValidationError({
                    "estado": "Complete el checklist clínico antes de firmar: "
                    + ", ".join(labels[field] for field in missing) + "."
                })
            if self.instance and any(
                field in attrs and attrs[field] != getattr(self.instance, field)
                for field in required
            ):
                raise ValidationError({"estado": "Guarde y revise los cambios antes de firmar el informe."})
        return attrs

    def _imagen(self, obj):
        if obj.imagen_origen_id:
            return obj.imagen_origen
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

    def get_hallazgos_ia(self, obj):
        img = self._imagen(obj)
        resultado = getattr(img, "resultado_cnn", None) if img else None
        return threshold_findings(resultado.patologias) if resultado else []

    def get_imagen_png_url(self, obj):
        img = self._imagen(obj)
        if img:
            request = self.context.get("request")
            from estudios.views import _get_imagen_url
            return _get_imagen_url(request, img)
        return None

    def get_medico_nombre(self, obj):
        if obj.medico:
            return obj.medico.get_full_name() or obj.medico.username
        return None
