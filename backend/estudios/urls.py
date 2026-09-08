from django.urls import path
from .views import UploadDICOMView, ImagenDICOMDetailView, ObtenerEstadoTareaView

urlpatterns = [
    path("upload/", UploadDICOMView.as_view(), name="upload-dicom"),
    path("imagen/<int:pk>/", ImagenDICOMDetailView.as_view(), name="imagen-detail"),
    path("tarea/<str:task_id>/", ObtenerEstadoTareaView.as_view(), name="estado-tarea"),
]
