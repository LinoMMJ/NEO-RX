from django.contrib import admin
from .models import InformePreliminar


@admin.register(InformePreliminar)
class InformePreliminarAdmin(admin.ModelAdmin):
    list_display = ("pk", "estudio", "medico", "estado", "fecha_creacion", "fecha_firmado")
    list_filter = ("estado",)
    search_fields = ("estudio__paciente__nombres", "estudio__paciente__apellidos")
