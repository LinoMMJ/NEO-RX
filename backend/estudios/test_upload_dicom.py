import io
from unittest.mock import patch

import numpy as np
from django.core.files.uploadedfile import SimpleUploadedFile
from pydicom.dataset import FileDataset, FileMetaDataset
from pydicom.uid import ExplicitVRLittleEndian, SecondaryCaptureImageStorage, generate_uid

from estudios.utils import dicom_pixel_array_2d
from estudios.validators import validate_file_comprehensive


def _rgb_dicom_bytes(body_part="CHEST"):
    checker = ((np.indices((32, 48)).sum(axis=0) % 2) * 255).astype(np.uint8)
    pixels = np.repeat(checker[..., None], 3, axis=2)
    meta = FileMetaDataset()
    meta.MediaStorageSOPClassUID = SecondaryCaptureImageStorage
    meta.MediaStorageSOPInstanceUID = generate_uid()
    meta.TransferSyntaxUID = ExplicitVRLittleEndian
    ds = FileDataset(None, {}, file_meta=meta, preamble=b"\0" * 128)
    ds.SOPClassUID = SecondaryCaptureImageStorage
    ds.Modality = "DX"
    ds.BodyPartExamined = body_part
    ds.Rows = pixels.shape[0]
    ds.Columns = pixels.shape[1]
    ds.SamplesPerPixel = 3
    ds.PhotometricInterpretation = "RGB"
    ds.PlanarConfiguration = 0
    ds.BitsAllocated = 8
    ds.BitsStored = 8
    ds.HighBit = 7
    ds.PixelRepresentation = 0
    ds.PixelData = pixels.tobytes()
    output = io.BytesIO()
    ds.save_as(output, enforce_file_format=True)
    return output.getvalue()


def test_rgb_dicom_without_optional_clinical_metadata_is_valid():
    upload = SimpleUploadedFile(
        "radiografia.dicom", _rgb_dicom_bytes(), content_type="application/dicom"
    )
    result = validate_file_comprehensive(upload)
    assert result["valid"] is True
    assert result["file_type"] == "dicom"
    assert result["errors"] == []
    assert result["warnings"]
    pixels = dicom_pixel_array_2d(result["dataset"])
    assert pixels.shape == (32, 48)
    assert pixels.dtype == np.float32

import pytest
from datetime import date
from django.test import override_settings
from django.urls import reverse

from estudios.models import ImagenDICOM
from diagnostico.models import ResultadoCNN
from informes.models import InformePreliminar
from pacientes.models import Estudio, Paciente

pytestmark = pytest.mark.django_db


@override_settings(NEORX_INFERENCE_MODE="inline")
def test_upload_endpoint_accepts_rgb_dicom(auth_medico, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    paciente = Paciente.objects.create(
        nombres="Paciente", apellidos="DICOM", ci="dicom-rgb-test",
        fecha_nacimiento=date(1980, 1, 1), genero="M",
    )
    estudio = Estudio.objects.create(paciente=paciente, fecha=date.today())
    archivo = SimpleUploadedFile(
        "radiografia.dicom", _rgb_dicom_bytes(), content_type="application/dicom"
    )

    model_result = {
        "hallazgos": [
            {"etiqueta": "Neumonía", "etiqueta_en": "Pneumonia",
             "probabilidad_estimada": 0.81, "detectado": True, "threshold_usado": 0.5},
        ],
        "probabilidades": {"Pneumonia": 0.81},
        "thresholds": {"Pneumonia": 0.5},
        "modelo": "densenet121-res224-all",
        "es_fine_tuned": False,
        "nota": "Resultado preliminar de prueba.",
    }
    with patch("diagnostico.services.DetectorTorax.desde_dicom", return_value=model_result):
        response = auth_medico.post(
            reverse("upload-dicom"),
            {"archivo": archivo, "estudio_id": estudio.pk},
            format="multipart",
        )

    assert response.status_code == 200, response.content
    assert response.json()["patologias"] == {"Neumonía": 0.81}
    assert response.json()["modelo"] == "densenet121-res224-all"
    assert response.json()["informe_id"]
    imagen = ImagenDICOM.objects.get(estudio=estudio)
    assert imagen.archivo_dicom.name.endswith(".dicom")
    assert imagen.archivo_png.name.endswith(".png")
    assert imagen.estado_procesamiento == "procesado"
    assert imagen.clasificacion_imagen == "chest_xray"
    assert imagen.apta_para_cnn is True
    assert ResultadoCNN.objects.filter(imagen=imagen).exists()
    assert InformePreliminar.objects.filter(estudio=estudio).exists()


@override_settings(NEORX_INFERENCE_MODE="inline")
def test_other_radiograph_is_stored_without_cnn(auth_medico, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    paciente = Paciente.objects.create(
        nombres="Paciente", apellidos="Rodilla", ci="xray-knee-test",
        fecha_nacimiento=date(1985, 2, 2), genero="F",
    )
    archivo = SimpleUploadedFile(
        "rodilla.dicom",
        _rgb_dicom_bytes(body_part="KNEE"),
        content_type="application/dicom",
    )

    response = auth_medico.post(
        reverse("upload-dicom"),
        {"archivo": archivo, "paciente_id": paciente.pk, "observaciones": "Control"},
        format="multipart",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == "STORED"
    assert data["clasificacion"]["classification"] == "other_xray"
    estudio = Estudio.objects.get(pk=data["estudio_id"])
    imagen = ImagenDICOM.objects.get(pk=data["imagen_id"])
    assert estudio.paciente == paciente
    assert estudio.estado == "registrado"
    assert "Rodilla" in estudio.tipo_estudio
    assert imagen.region_anatomica == "Rodilla"
    assert imagen.apta_para_cnn is False
    assert imagen.estado_procesamiento == "sin_analisis"
    assert not ResultadoCNN.objects.filter(imagen=imagen).exists()
    assert not InformePreliminar.objects.filter(estudio=estudio).exists()


@override_settings(NEORX_INFERENCE_MODE="inline")
def test_study_registration_without_ai_never_runs_cnn(auth_medico, tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    paciente = Paciente.objects.create(
        nombres="Paciente", apellidos="Registro", ci="registro-sin-ia-test",
        fecha_nacimiento=date(1985, 2, 2), genero="F",
    )
    archivo = SimpleUploadedFile(
        "mano.dicom", _rgb_dicom_bytes(body_part="HAND"), content_type="application/dicom",
    )

    response = auth_medico.post(
        reverse("upload-dicom"),
        {
            "archivo": archivo,
            "paciente_id": paciente.pk,
            "registro_sin_ia": "true",
            "tipo_estudio": "Radiografía de mano derecha",
            "observaciones": "Control traumatológico",
        },
        format="multipart",
    )

    assert response.status_code == 201, response.content
    data = response.json()
    assert data["status"] == "STORED"
    assert data["registro_sin_ia"] is True
    estudio = Estudio.objects.get(pk=data["estudio_id"])
    imagen = ImagenDICOM.objects.get(pk=data["imagen_id"])
    assert estudio.tipo_estudio == "Radiografía de mano derecha"
    assert estudio.estado == "registrado"
    assert estudio.observaciones == "Control traumatológico"
    assert imagen.apta_para_cnn is False
    assert imagen.estado_procesamiento == "sin_analisis"
    assert "solicitud del usuario" in imagen.motivo_no_cnn
    assert not ResultadoCNN.objects.filter(imagen=imagen).exists()
    assert not InformePreliminar.objects.filter(estudio=estudio).exists()


@override_settings(NEORX_INFERENCE_MODE="inline")
def test_non_radiograph_is_rejected_without_database_records(auth_medico, tmp_path, settings):
    from PIL import Image

    settings.MEDIA_ROOT = tmp_path
    paciente = Paciente.objects.create(
        nombres="Paciente", apellidos="Foto", ci="not-xray-test",
        fecha_nacimiento=date(1990, 3, 3), genero="M",
    )
    rgb = np.zeros((180, 260, 3), dtype=np.uint8)
    rgb[:, :, 0] = 240
    rgb[:, :, 1] = np.arange(260, dtype=np.uint8)[None, :]
    rgb[:, :, 2] = 30
    buffer = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(buffer, format="PNG")
    archivo = SimpleUploadedFile("fotografia.png", buffer.getvalue(), content_type="image/png")
    studies_before = Estudio.objects.count()
    images_before = ImagenDICOM.objects.count()

    response = auth_medico.post(
        reverse("upload-dicom"),
        {"archivo": archivo, "paciente_id": paciente.pk},
        format="multipart",
    )

    assert response.status_code == 422, response.content
    assert response.json()["codigo"] == "no_radiografia"
    assert Estudio.objects.count() == studies_before
    assert ImagenDICOM.objects.count() == images_before
