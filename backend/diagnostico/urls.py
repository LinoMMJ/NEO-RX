from django.urls import path
from .views import ResultadoCNNView, GradCAMView
from .views_niveles import NivelesClinicosConfigView, ClasificarProbabilidadesView

urlpatterns = [
    path("resultado/<int:imagen_id>/", ResultadoCNNView.as_view(), name="resultado-cnn"),
    path("gradcam/", GradCAMView.as_view(), name="gradcam"),
    path("niveles-clinicos/", NivelesClinicosConfigView.as_view(), name="niveles-clinicos"),
    path("clasificar/", ClasificarProbabilidadesView.as_view(), name="clasificar-probabilidades"),
]
