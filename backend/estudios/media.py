"""Private delivery of registered image files; storage bytes remain unencrypted."""
import mimetypes
from pathlib import Path
from django.conf import settings
from django.http import FileResponse
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound
from neorx.permissions import ClinicalRecordPermission
from .models import ImagenDICOM


class PrivateMediaView(APIView):
    permission_classes = [ClinicalRecordPermission]

    def get(self, request, path):
        root = Path(settings.MEDIA_ROOT).resolve()
        candidate = (root / path).resolve()
        if not candidate.is_relative_to(root):
            raise NotFound("Archivo no encontrado.")
        image = ImagenDICOM.objects.filter(Q(archivo_dicom=path) | Q(archivo_png=path)).first()
        if image is None:
            raise NotFound("Archivo no encontrado.")
        field = image.archivo_png if image.archivo_png.name == path else image.archivo_dicom
        try:
            source = field.storage.open(field.name, "rb")
        except (FileNotFoundError, OSError):
            raise NotFound("Archivo no encontrado.") from None
        dicom = path.lower().endswith((".dcm", ".dicom"))
        response = FileResponse(source, content_type="application/dicom" if dicom else
                                mimetypes.guess_type(path)[0] or "application/octet-stream",
                                as_attachment=dicom, filename=Path(path).name)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response
