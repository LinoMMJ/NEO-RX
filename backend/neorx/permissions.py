from rest_framework.permissions import BasePermission, SAFE_METHODS


class MedicalWritePermission(BasePermission):
    """Only radiologists can change clinical reports."""
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and
                    (request.method in SAFE_METHODS or request.user.rol == "medico"))


class ReceptionUploadPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and
                    request.user.rol in {"recepcionista", "medico"})


class ClinicalRecordPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user.is_authenticated and request.user.is_active and
                    request.user.rol in {"medico", "recepcionista", "administrador"})
