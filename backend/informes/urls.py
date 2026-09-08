from django.urls import path
from .views import GenerarInformeView, InformePreliminarDetailView, DescargarInformePDFView

urlpatterns = [
    path("generar/", GenerarInformeView.as_view(), name="generar-informe"),
    path("<int:pk>/", InformePreliminarDetailView.as_view(), name="informe-detail"),
    path("<int:pk>/descargar/", DescargarInformePDFView.as_view(), name="descargar-informe-pdf"),
]
