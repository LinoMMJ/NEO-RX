"""
pytest configuration for Neo RX backend.

Usa pytest-django con DJANGO_SETTINGS_MODULE=neorx.settings (definido en pytest.ini).
Define fixtures compartidas de autenticación por rol para las pruebas de API.
"""

import pytest
from rest_framework.test import APIClient

from accounts.models import CustomUser


@pytest.fixture
def api_client():
    """Cliente DRF sin autenticación."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Usuario administrador."""
    return CustomUser.objects.create_user(
        username="admin_test", email="admin@test.com", password="admin123",
        first_name="Admin", last_name="Test", rol="administrador",
    )


@pytest.fixture
def medico_user(db):
    """Usuario médico radiólogo."""
    return CustomUser.objects.create_user(
        username="medico_test", email="medico@test.com", password="medico123",
        first_name="Medico", last_name="Test", rol="medico",
    )


@pytest.fixture
def recepcionista_user(db):
    """Usuario recepcionista."""
    return CustomUser.objects.create_user(
        username="recepcionista_test", email="recep@test.com", password="recep123",
        first_name="Recep", last_name="Test", rol="recepcionista",
    )


@pytest.fixture
def auth_admin(api_client, admin_user):
    """Cliente autenticado como administrador."""
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def auth_medico(api_client, medico_user):
    """Cliente autenticado como médico."""
    api_client.force_authenticate(user=medico_user)
    return api_client


@pytest.fixture
def auth_recepcionista(api_client, recepcionista_user):
    """Cliente autenticado como recepcionista."""
    api_client.force_authenticate(user=recepcionista_user)
    return api_client

@pytest.fixture
def auth_client(auth_medico):
    return auth_medico


@pytest.fixture
def imagen_dicom(db):
    from pacientes.models import Paciente, Estudio
    from estudios.models import ImagenDICOM
    from datetime import date
    paciente = Paciente.objects.create(nombres="Fixture", apellidos="Paciente", ci="fixture-ci",
                                       fecha_nacimiento=date(1980, 1, 1), genero="M")
    estudio = Estudio.objects.create(paciente=paciente, fecha=date.today())
    return ImagenDICOM.objects.create(estudio=estudio, archivo_dicom="dicom/unit-test.dcm",
                                      es_nitida=True, tipo_proyeccion="PA", estado_procesamiento="procesado")


@pytest.fixture
def imagen_con_resultado(imagen_dicom):
    from diagnostico.models import ResultadoCNN
    ResultadoCNN.objects.create(imagen=imagen_dicom, patologias={"Neumonía": 0.85, "Derrame pleural": 0.12},
                                tiempo_inferencia_seg=None)
    return imagen_dicom


@pytest.fixture(autouse=True)
def isolate_cnn_singleton(monkeypatch):
    from diagnostico.services import DetectorTorax
    for attr, value in {"_modelo": None, "_transform": None, "_labels_es": {}, "_thresholds": {}, "_is_finetuned": False}.items():
        monkeypatch.setattr(DetectorTorax, attr, value)
    monkeypatch.delenv("NEORX_MODEL_PATH", raising=False)
    import torchxrayvision as xrv
    def deny_real_model(*args, **kwargs):
        raise AssertionError("Esta suite comprueba software; no permite descargar/cargar pesos reales.")
    monkeypatch.setattr(xrv.models, "ResNet", deny_real_model)
