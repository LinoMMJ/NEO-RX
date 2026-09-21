from datetime import date
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from pacientes.models import Paciente, Estudio
from estudios.models import ImagenDICOM
from informes.models import InformePreliminar
from neorx.models import AuditLog

pytestmark = pytest.mark.django_db

@pytest.mark.parametrize("role", ["medico", "recepcionista", "administrador"])
def test_activity_scope_and_privacy(role):
    User = get_user_model()
    own = User.objects.create_user(username="own", rol=role)
    other = User.objects.create_user(username="other", rol="medico")
    event = AuditLog.objects.create(user=own, user_role=role, action="update", resource_type="paciente", resource_id="42", before={"ci": "sensitive"}, metadata={"token": "sensitive"})
    AuditLog.objects.create(user=other, action="login", resource_type="auth")
    client = APIClient(); client.force_authenticate(own)
    response = client.get("/api/actividad/")
    assert response.status_code == 200
    assert response.data["count"] == (2 if role == "administrador" else 1)
    assert set(response.data["results"][0]) == {"id", "timestamp", "actor", "user_role", "action", "resource_type", "resource_id"}
    assert client.post("/api/actividad/", {}).status_code == 405
    assert client.get("/api/actividad/?action=update").data["results"][0]["id"] == event.pk


def test_summary_counts_and_queues_do_not_duplicate_images():
    User = get_user_model(); user = User.objects.create_user(username="med", rol="medico")
    client = APIClient(); client.force_authenticate(user)
    for i in range(25):
        patient = Paciente.objects.create(nombres="Test", apellidos=str(i), ci=f"review{i}", fecha_nacimiento=date(1990,1,1), genero="M")
    pending = Estudio.objects.create(paciente=patient, fecha=date.today())
    completed = Estudio.objects.create(paciente=patient, fecha=date.today(), estado="completado")
    repeat = Estudio.objects.create(paciente=patient, fecha=date.today(), estado="requiere_repeticion")
    InformePreliminar.objects.create(estudio=completed, estado="firmado")
    for _ in range(2):
        latest_image = ImagenDICOM.objects.create(estudio=pending, archivo_dicom="test.dcm", estado_procesamiento="error")
    summary = client.get("/api/workspace/resumen/").data
    assert summary["pacientes_total"] == 25
    assert summary["estudios_total"] == 3
    assert summary["informes_pendientes"] == 1
    assert summary["errores_procesamiento"] == 1
    assert "administracion" not in summary
    for queue, expected in [("informes",pending.pk),("errores",pending.pk),("repeticion",repeat.pk)]:
        response = client.get("/api/pacientes/estudios/", {"cola":queue})
        assert response.status_code == 200
        assert response.data["count"] == 1
        assert response.data["results"][0]["id"] == expected
        assert response.data["results"][0]["paciente_nombre"] == "Test 24"
        if queue in ("informes", "errores"):
            assert response.data["results"][0]["ultima_imagen_id"] == latest_image.pk
    assert client.get("/api/pacientes/estudios/?cola=invalid").status_code == 400
    assert client.get("/api/pacientes/estudios/?paciente=invalid").status_code == 400
    user.rol="administrador"; user.save()
    assert client.get("/api/workspace/resumen/").data["administracion"]["usuarios_total"] == 1


@pytest.mark.parametrize("url", ["/api/actividad/", "/api/workspace/resumen/", "/api/pacientes/", "/api/pacientes/estudios/"])
def test_date_validation(url, medico_user):
    client = APIClient(); client.force_authenticate(medico_user)
    assert client.get(url, {"fecha_desde":"invalid"}).status_code == 400
    assert client.get(url, {"fecha_desde":"2026-09-18", "fecha_hasta":"2026-09-01"}).status_code == 400


@pytest.mark.parametrize("url", ["/api/actividad/", "/api/workspace/resumen/"])
def test_workspace_requires_active_clinical_role(url):
    client=APIClient()
    assert client.get(url).status_code == 401
    user=get_user_model().objects.create_user(username="invalid", rol="invalid")
    client.force_authenticate(user)
    assert client.get(url).status_code == 403
    user.rol="medico"; user.is_active=False; user.save()
    assert client.get(url).status_code == 403
