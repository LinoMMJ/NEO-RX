"""
Tests unitarios para app diagnostico.
"""

import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from pacientes.models import Paciente, Estudio

pytestmark = pytest.mark.django_db


class TestResultadoCNNModel:
    """Tests del modelo ResultadoCNN."""

    def test_crear_resultado_cnn(self, imagen_dicom):
        resultado = ResultadoCNN.objects.create(
            imagen=imagen_dicom,
            patologias={"Neumonía": 0.85, "Derrame pleural": 0.12},
            tiempo_inferencia_seg=0.45,
        )
        assert resultado.imagen == imagen_dicom
        assert resultado.patologias["Neumonía"] == 0.85
        assert resultado.tiempo_inferencia_seg == 0.45


class TestDetectorTorax:
    """Tests del servicio DetectorTorax (con mock)."""

    @patch("diagnostico.services.xrv")
    @patch("diagnostico.services.torch")
    def test_cargar_modelo_singleton(self, mock_torch, mock_xrv):
        from diagnostico.services import DetectorTorax

        mock_model = MagicMock()
        mock_model.pathologies = ["Pneumonia", "Effusion"]
        mock_xrv.models.ResNet.return_value = mock_model

        # Primera carga
        modelo1 = DetectorTorax.cargar()
        assert modelo1 is mock_model

        # Segunda carga debe retornar el mismo (singleton)
        modelo2 = DetectorTorax.cargar()
        assert modelo2 is mock_model
        assert mock_xrv.models.ResNet.call_count == 1

    @patch("diagnostico.services.DetectorTorax.cargar")
    def test_predecir_desde_png(self, mock_cargar):
        from diagnostico.services import DetectorTorax
        import numpy as np

        mock_model = MagicMock()
        mock_model.pathologies = ["Pneumonia", "Effusion", "Atelectasis"]
        mock_model.return_value = [[0.8, 0.1, 0.05]]
        mock_cargar.return_value = mock_model

        img = np.random.rand(512, 512).astype(np.float32)
        resultado = DetectorTorax.predecir(img, 255.0)

        assert "Neumonía" in resultado
        assert resultado["Neumonía"] == 0.8
        assert resultado["Derrame pleural"] == 0.1


class TestDiagnosticoAPI:
    """Tests de la API de diagnóstico."""

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
    def estudio_con_imagen(self, medico_user):
        paciente = Paciente.objects.create(
            nombres="Test", apellidos="Paciente", ci="99999999",
            fecha_nacimiento="1980-01-01", genero="M"
        )
        estudio = Estudio.objects.create(
            paciente=paciente, fecha="2024-01-15",
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

    def test_resultado_cnn_view(self, auth_client, estudio_con_imagen):
        url = reverse("resultado-cnn", kwargs={"imagen_id": estudio_con_imagen.id})
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "patologias" in data
        assert "Neumonía" in data["patologias"]
        assert data["estado_procesamiento"] == "procesado"

    def test_gradcam_view(self, auth_client, estudio_con_imagen):
        with patch("diagnostico.views.DetectorTorax.cargar") as mock_cargar, \
             patch("diagnostico.views.GeneradorGradCAM.calcular") as mock_calcular, \
             patch("diagnostico.views.GeneradorGradCAM.get_centroide") as mock_centroide, \
             patch("diagnostico.views.GeneradorGradCAM.overlay_base64") as mock_overlay, \
             patch("diagnostico.views.GeneradorGradCAM.overlay_solo_heatmap_base64") as mock_solo:

            from diagnostico.services import PATOLOGIAS_NEUMOLOGIA
            mock_model = MagicMock()
            mock_model.pathologies = list(PATOLOGIAS_NEUMOLOGIA.keys())
            mock_cargar.return_value = mock_model

            mock_calcular.return_value = np.random.rand(512, 512).astype(np.float32)
            mock_centroide.return_value = {"x": 256, "y": 256}
            mock_overlay.return_value = "data:image/png;base64,mock"
            mock_solo.return_value = "data:image/png;base64,mock"

            url = reverse("gradcam")
            response = auth_client.get(url, {"imagen_id": estudio_con_imagen.id})
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "overlay" in data
            assert "centroide" in data

    def test_niveles_clinicos_config(self, auth_client):
        url = reverse("niveles-clinicos")
        response = auth_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "niveles_generales" in data
        assert "alto" in data["niveles_generales"]
        assert "umbrales_por_patologia" in data


class TestNivelesClinicos:
    """Tests de la lógica de niveles clínicos."""

    def test_clasificar_probabilidad_alto(self):
        from diagnostico.niveles import clasificar_probabilidad
        nivel = clasificar_probabilidad("Neumonía", 0.80)
        assert nivel.etiqueta == "alto"
        assert nivel.color == "danger"

    def test_clasificar_probabilidad_moderado(self):
        from diagnostico.niveles import clasificar_probabilidad
        nivel = clasificar_probabilidad("Neumonía", 0.50)
        assert nivel.etiqueta == "moderado"
        assert nivel.color == "orange"

    def test_clasificar_probabilidad_leve(self):
        from diagnostico.niveles import clasificar_probabilidad
        nivel = clasificar_probabilidad("Neumonía", 0.30)
        assert nivel.etiqueta == "leve"
        assert nivel.color == "warning"

    def test_clasificar_probabilidad_marginal(self):
        from diagnostico.niveles import clasificar_probabilidad
        nivel = clasificar_probabilidad("Neumonía", 0.10)
        assert nivel.etiqueta == "marginal"
        assert nivel.color == "slate"

    def test_umbrales_especificos_patologia(self):
        from diagnostico.niveles import obtener_umbrales, clasificar_probabilidad
        # Neumonía tiene umbrales más conservadores
        u = obtener_umbrales("Neumonía")
        assert u["alto"] == 0.60
        assert u["moderado"] == 0.35
        assert u["leve"] == 0.15

        # Neumotórax es más crítico
        u = obtener_umbrales("Neumotórax")
        assert u["alto"] == 0.70
        assert u["moderado"] == 0.45

    def test_clasificar_todas(self):
        from diagnostico.niveles import clasificar_todas
        patologias = {
            "Neumonía": 0.85,
            "Derrame pleural": 0.30,
            "Atelectasia": 0.10,
        }
        resultado = clasificar_todas(patologias)
        assert resultado["Neumonía"]["nivel"] == "alto"
        assert resultado["Derrame pleural"]["nivel"] == "moderado"
        assert resultado["Atelectasia"]["nivel"] == "marginal"