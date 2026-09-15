from django.urls import path
from .views import (
    GenerarInformeView,
    InformePreliminarDetailView,
    DescargarInformePDFView,
    DescargarInformeDICOMSRView,
)

urlpatterns = [
    path("generar/", GenerarInformeView.as_view(), name="generar-informe"),
    path("<int:pk>/", InformePreliminarDetailView.as_view(), name="informe-detail"),
    path("<int:pk>/pdf/", DescargarInformePDFView.as_view(), name="descargar-informe-pdf"),
    path("<int:pk>/dicom-sr/", DescargarInformeDICOMSRView.as_view(), name="descargar-informe-dicom-sr"),
]
