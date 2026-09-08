from django.contrib import admin
from .models import ImagenDICOM


@admin.register(ImagenDICOM)
class ImagenDICOMAdmin(admin.ModelAdmin):
    list_display = ("pk", "estudio", "fecha_subida", "es_nitida", "varianza_laplaciana", "estado_procesamiento")
    list_filter = ("estado_procesamiento", "es_nitida")
