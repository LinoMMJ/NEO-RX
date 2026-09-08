from django.contrib import admin
from .models import ResultadoCNN


@admin.register(ResultadoCNN)
class ResultadoCNNAdmin(admin.ModelAdmin):
    list_display = ("pk", "imagen", "fecha_analisis", "tiempo_inferencia_seg")
    readonly_fields = ("patologias", "fecha_analisis", "tiempo_inferencia_seg")
