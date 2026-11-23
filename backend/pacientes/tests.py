"""
Tests unitarios para app pacientes.
"""

import pytest
from datetime import date, timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from pacientes.models import Paciente, Estudio


pytestmark = pytest.mark.django_db


class TestPacienteModel:
    """Tests del modelo Paciente."""

    def test_crear_paciente(self):
        paciente = Paciente.objects.create(
            nombres="Juan Carlos",
            apellidos="Pérez López",
            ci="12345678",
            fecha_nacimiento="1980-05-15",
            genero="M",
            telefono="70123456",
        )
        assert paciente.nombres == "Juan Carlos"
        assert paciente.ci == "12345678"
        assert str(paciente) == "Juan Carlos Pérez López (CI: 12345678)"

    def test_ci_unico(self):
        Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )
        with pytest.raises(Exception):
            Paciente.objects.create(
                nombres="María", apellidos="García", ci="12345678",
                fecha_nacimiento="1990-01-01", genero="F"
            )


class TestPacienteAPI:
    """Tests de la API REST de pacientes."""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def admin_user(self):
        from accounts.models import CustomUser
        return CustomUser.objects.create_superuser(
            username="admin", email="admin@test.com", password="admin123",
            rol="administrador"
        )

    @pytest.fixture
    def auth_client(self, api_client, admin_user):
        api_client.force_authenticate(user=admin_user)
        return api_client

    def test_list_pacientes(self, auth_client):
        Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )
        Paciente.objects.create(
            nombres="María", apellidos="García", ci="87654321",
            fecha_nacimiento="1990-01-01", genero="F"
        )

        url = reverse("paciente-list")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["count"] == 2

    def test_create_paciente(self, auth_client):
        url = reverse("paciente-list")
        data = {
            "nombres": "Carlos",
            "apellidos": "Rodríguez",
            "ci": "11223344",
            "fecha_nacimiento": "1985-03-20",
            "genero": "M",
            "telefono": "71234567",
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["nombres"] == "Carlos"
        assert Paciente.objects.filter(ci="11223344").exists()

    def test_create_paciente_ci_duplicado(self, auth_client):
        Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )
        url = reverse("paciente-list")
        data = {
            "nombres": "Otro", "apellidos": "Apellido", "ci": "12345678",
            "fecha_nacimiento": "1990-01-01", "genero": "F"
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_fecha_nacimiento_acepta_100_pero_rechaza_mas_de_100(self, auth_client):
        today = timezone.localdate()
        exactly_100 = date(today.year - 100, today.month, today.day)
        over_100 = date(today.year - 101, today.month, today.day)
        base = {"nombres": "Edad", "apellidos": "Límite", "genero": "Otro"}

        accepted = auth_client.post(reverse("paciente-list"), {
            **base, "ci": "AGE-100", "fecha_nacimiento": exactly_100.isoformat(),
        }, format="json")
        rejected = auth_client.post(reverse("paciente-list"), {
            **base, "ci": "AGE-101", "fecha_nacimiento": over_100.isoformat(),
        }, format="json")

        assert accepted.status_code == status.HTTP_201_CREATED
        assert rejected.status_code == status.HTTP_400_BAD_REQUEST
        assert "más de 100 años" in str(rejected.data["errors"]["fecha_nacimiento"][0])

    def test_rechaza_fecha_futura_y_campos_personales_mal_formados(self, auth_client):
        future = timezone.localdate() + timedelta(days=1)
        response = auth_client.post(reverse("paciente-list"), {
            "nombres": "1234", "apellidos": "Apellido<script>", "ci": "CI/INVALIDO",
            "fecha_nacimiento": future.isoformat(), "genero": "M", "telefono": "12-AB",
        }, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert {"nombres", "apellidos", "ci", "fecha_nacimiento", "telefono"}.issubset(response.data["errors"])

    def test_search_paciente_by_ci(self, auth_client):
        Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )
        url = reverse("paciente-list")
        response = auth_client.get(url, {"search": "12345678"})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 1
        assert response.json()["results"][0]["ci"] == "12345678"


class TestEstudioModel:
    """Tests del modelo Estudio."""

    def test_crear_estudio(self):
        paciente = Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )
        estudio = Estudio.objects.create(
            paciente=paciente,
            fecha="2024-01-15",
            tipo_estudio="Radiografía de Tórax PA",
            observaciones="Paciente con tos persistente",
        )
        assert estudio.paciente == paciente
        assert estudio.estado == "pendiente"
        assert "Radiografía" in str(estudio)


class TestEstudioAPI:
    """Tests de la API REST de estudios."""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def paciente(self):
        return Paciente.objects.create(
            nombres="Juan", apellidos="Pérez", ci="12345678",
            fecha_nacimiento="1980-05-15", genero="M"
        )

    @pytest.fixture
    def auth_client(self, api_client):
        from accounts.models import CustomUser
        user = CustomUser.objects.create_user(
            username="medico1", password="medico123", rol="medico"
        )
        api_client.force_authenticate(user=user)
        return api_client

    def test_create_estudio(self, auth_client, paciente):
        url = reverse("estudio-list")
        data = {
            "paciente": paciente.id,
            "fecha": "2024-01-15",
            "tipo_estudio": "Radiografía de Tórax PA",
            "observaciones": "Control rutinario",
        }
        response = auth_client.post(url, data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.json()["paciente"] == paciente.id

    def test_rechaza_fecha_de_estudio_futura_o_anterior_al_nacimiento(self, auth_client, paciente):
        url = reverse("estudio-list")
        common = {"paciente": paciente.id, "tipo_estudio": "Radiografía de tórax"}
        future = auth_client.post(url, {
            **common, "fecha": (timezone.localdate() + timedelta(days=1)).isoformat(),
        }, format="json")
        before_birth = auth_client.post(url, {
            **common, "fecha": "1970-01-01",
        }, format="json")
        assert future.status_code == status.HTTP_400_BAD_REQUEST
        assert before_birth.status_code == status.HTTP_400_BAD_REQUEST
        assert "fecha" in future.data["errors"] and "fecha" in before_birth.data["errors"]

    def test_filter_estudios_by_paciente(self, auth_client, paciente):
        Estudio.objects.create(paciente=paciente, fecha="2024-01-15", tipo_estudio="Rx Tórax")
        Estudio.objects.create(paciente=paciente, fecha="2024-01-16", tipo_estudio="Rx Columna")

        url = reverse("estudio-list")
        response = auth_client.get(url, {"paciente": paciente.id})
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["count"] == 2
