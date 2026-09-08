from django.urls import path
from rest_framework.routers import SimpleRouter
from .views import PacienteViewSet, EstudioViewSet, BuscarPacienteView

# Orden crítico: rutas específicas (estudios/, buscar/) ANTES del router
# de pacientes, cuyo patrón genérico ^(?P<pk>[^/.]+)/$ atraparía esos
# prefijos como si fueran un pk y devolvería 404.
router_estudios = SimpleRouter()
router_estudios.register(r"estudios", EstudioViewSet, basename="estudio")

router_pacientes = SimpleRouter()
router_pacientes.register(r"", PacienteViewSet, basename="paciente")

urlpatterns = (
    [path("buscar/", BuscarPacienteView.as_view(), name="buscar-paciente")]
    + router_estudios.urls
    + router_pacientes.urls
)
