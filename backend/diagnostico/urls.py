from django.urls import path
from .views import ResultadoCNNView, GradCAMView

urlpatterns = [
    path("resultado/<int:imagen_id>/", ResultadoCNNView.as_view(), name="resultado-cnn"),
    path("gradcam/", GradCAMView.as_view(), name="gradcam"),
]
