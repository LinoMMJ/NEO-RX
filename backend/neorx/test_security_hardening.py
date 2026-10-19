from django.test import override_settings

from diagnostico.serializers import ResultadoCNNSerializer
from estudios.serializers import ImagenDICOMSerializer
from informes.serializers import InformePreliminarSerializer
from pacientes.serializers import EstudioSerializer, PacienteSerializer


def test_internal_analysis_fields_are_read_only():
    assert set(ImagenDICOMSerializer.Meta.read_only_fields) == set(ImagenDICOMSerializer.Meta.fields)
    assert set(ResultadoCNNSerializer.Meta.read_only_fields) == set(ResultadoCNNSerializer.Meta.fields)


def test_server_controlled_fields_cannot_be_changed():
    assert {"informe_id", "informe_estado", "ultima_imagen_id"}.issubset(
        EstudioSerializer.Meta.read_only_fields
    )
    assert {"estudio", "medico", "fecha_firmado", "probabilidades"}.issubset(
        InformePreliminarSerializer.Meta.read_only_fields
    )


def test_plain_text_rejects_control_characters(db):
    serializer = PacienteSerializer(data={
        "nombres": "Nombre\x00oculto",
        "apellidos": "Prueba",
        "ci": "SECURITY-001",
        "fecha_nacimiento": "1990-01-01",
        "genero": "M",
    })
    assert not serializer.is_valid()
    assert "nombres" in serializer.errors


@override_settings(DEBUG=False)
def test_security_headers_middleware(rf):
    from django.http import JsonResponse
    from neorx.security import SecurityHeadersMiddleware

    response = SecurityHeadersMiddleware(lambda request: JsonResponse({"ok": True}))(rf.get("/api/test/"))
    assert "unsafe-eval" not in response["Content-Security-Policy"]
    assert response["X-Frame-Options"] == "DENY"
    assert response["Cross-Origin-Resource-Policy"] == "same-origin"
    assert response["Cache-Control"].startswith("no-store")
