from django.urls import path
from .views import (
    UploadDICOMView,
    ImagenDICOMDetailView,
    ImagenDICOMListView,
    ObtenerEstadoTareaView,
)

urlpatterns = [
    path("upload/", UploadDICOMView.as_view(), name="upload-dicom"),
    path("imagen/<int:pk>/", ImagenDICOMDetailView.as_view(), name="imagen-detail"),
    path("imagenes/", ImagenDICOMListView.as_view(), name="imagen-list"),
    path("tarea/<str:task_id>/", ObtenerEstadoTareaView.as_view(), name="estado-tarea"),
]
