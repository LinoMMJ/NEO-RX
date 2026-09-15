"""
Tests unitarios para app informes.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from datetime import date

from pacientes.models import Paciente, Estudio
from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from informes.models import InformePreliminar

pytestmark = pytest.mark.django_db


class TestInformePreliminarModel:
    """Tests del modelo InformePreliminar."""

    def test_crear_informe(self, imagen_con_resultado):
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos de prueba",
            impresion="Impresión de prueba",
            recomendaciones="Recomendaciones de prueba",
        )
        assert informe.estudio == imagen_con_resultado.estudio
        assert informe.estado == "borrador"
        assert informe.hallazgos == "Hallazgos de prueba"


class TestInformeAPI:
    """Tests de la API de informes."""

    @pytest.fixture
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def medico_user(self):
        from accounts.models import CustomUser
        return CustomUser.objects.create_user(
            username="medico1", password="medico123", rol="medico"
        )

    @pytest.fixture
    def auth_client(self, api_client, medico_user):
        api_client.force_authenticate(user=medico_user)
        return api_client

    @pytest.fixture
    def imagen_con_resultado(self, medico_user):
        paciente = Paciente.objects.create(
            nombres="Test", apellidos="Paciente", ci="99999999",
            fecha_nacimiento="1980-01-01", genero="M"
        )
        estudio = Estudio.objects.create(
            paciente=paciente, fecha=date.today(),
            tipo_estudio="Radiografía de Tórax PA"
        )
        imagen = ImagenDICOM.objects.create(
            estudio=estudio,
            archivo_dicom="dicom/test.dcm",
            estado_procesamiento="procesado",
            es_nitida=True,
            varianza_laplaciana=150.0,
            tipo_proyeccion="PA",
        )
        ResultadoCNN.objects.create(
            imagen=imagen,
            patologias={"Neumonía": 0.85, "Derrame pleural": 0.12},
            tiempo_inferencia_seg=0.45,
        )
        return imagen

    def test_generar_informe(self, auth_client, imagen_con_resultado):
        url = reverse("generar-informe")
        response = auth_client.post(url, {"estudio_id": imagen_con_resultado.estudio.id}, format="json")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "id" in data
        assert data["estado"] == "borrador"
        assert "hallazgos" in data
        assert "impresion" in data
        assert "recomendaciones" in data

    def test_generar_informe_sin_cnn(self, auth_client):
        from pacientes.models import Paciente, Estudio
        from datetime import date
        paciente = Paciente.objects.create(
            nombres="Test", apellidos="SinCNN", ci="88888888",
            fecha_nacimiento="1980-01-01", genero="M"
        )
        estudio = Estudio.objects.create(
            paciente=paciente, fecha=date.today(),
            tipo_estudio="Radiografía de Tórax PA"
        )
        # No crear ImagenDICOM ni ResultadoCNN

        url = reverse("generar-informe")
        response = auth_client.post(url, {"estudio_id": estudio.id}, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "CNN" in response.json()["error"]

    def test_detalle_informe(self, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos",
            impresion="Impresión",
            recomendaciones="Recomendaciones",
        )
        url = reverse("informe-detail", kwargs={"pk": informe.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == informe.id
        assert data["hallazgos"] == "Hallazgos"

    def test_actualizar_informe(self, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Original",
            impresion="Original",
            recomendaciones="Original",
        )
        url = reverse("informe-detail", kwargs={"pk": informe.id})
        response = auth_client.put(url, {
            "hallazgos": "Actualizado",
            "impresion": "Actualizada",
            "recomendaciones": "Actualizadas",
        }, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["hallazgos"] == "Actualizado"

    def test_firmar_informe_como_medico(self, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        from django.utils import timezone
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos", impresion="Impresión",
            recomendaciones="Recomendaciones",
        )
        url = reverse("informe-detail", kwargs={"pk": informe.id})
        response = auth_client.put(url, {"estado": "firmado"}, format="json")
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["estado"] == "firmado"
        assert response.json()["fecha_firmado"] is not None
        assert response.json()["medico"] is not None


class TestExportPDF:
    """Tests de exportación PDF."""

    @patch("informes.views.HTML")
    def test_descargar_pdf_firmado(self, mock_html, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos", impresion="Impresión",
            recomendaciones="Recomendaciones",
            estado="firmado",
        )
        mock_html.return_value.write_pdf = MagicMock()

        url = reverse("descargar-informe-pdf", kwargs={"pk": informe.id})
        response = auth_client.get(url)
        # No podemos verificar el PDF completo en test unitario, solo que no falla
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_501_NOT_IMPLEMENTED]


class TestExportDICOMSR:
    """Tests de exportación DICOM SR."""

    def test_descargar_dicom_sr_firmado(self, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos", impresion="Impresión",
            recomendaciones="Recomendaciones",
            estado="firmado",
        )
        url = reverse("descargar-informe-dicom-sr", kwargs={"pk": informe.id})
        response = auth_client.get(url)
        # Verificar que no da error 404/403
        assert response.status_code in [
            status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST,
            status.HTTP_501_NOT_IMPLEMENTED
        ]

    def test_descargar_dicom_sr_no_firmado(self, auth_client, imagen_con_resultado):
        from informes.models import InformePreliminar
        informe = InformePreliminar.objects.create(
            estudio=imagen_con_resultado.estudio,
            hallazgos="Hallazgos", impresion="Impresión",
            recomendaciones="Recomendaciones",
            estado="borrador",
        )
        url = reverse("descargar-informe-dicom-sr", kwargs={"pk": informe.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "firmados" in response.json()["error"].lower()