from django.contrib import admin
from .models import Paciente, Estudio


@admin.register(Paciente)
class PacienteAdmin(admin.ModelAdmin):
    list_display = ("nombres", "apellidos", "ci", "fecha_nacimiento", "genero")
    search_fields = ("nombres", "apellidos", "ci")


@admin.register(Estudio)
class EstudioAdmin(admin.ModelAdmin):
    list_display = ("paciente", "tipo_estudio", "fecha", "estado")
    list_filter = ("estado",)
    search_fields = ("paciente__nombres", "paciente__apellidos", "paciente__ci")
