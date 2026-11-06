from django.urls import path
from .views import (
    UploadDICOMView,
    DICOMPreviewView,
    ImagenDICOMDetailView,
    ImagenDICOMListView,
    ObtenerEstadoTareaView,
    RetryImageView,
)

urlpatterns = [
    path("vista-previa/", DICOMPreviewView.as_view(), name="dicom-preview"),
    path("upload/", UploadDICOMView.as_view(), name="upload-dicom"),
    path("imagen/<int:pk>/", ImagenDICOMDetailView.as_view(), name="imagen-detail"),
    path("imagen/<int:pk>/reintentar/", RetryImageView.as_view(), name="imagen-retry"),
    path("imagenes/", ImagenDICOMListView.as_view(), name="imagen-list"),
    path("tarea/<str:task_id>/", ObtenerEstadoTareaView.as_view(), name="estado-tarea"),
]
