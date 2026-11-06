"""Real-weight local software smoke; synthetic data, in-memory DB, temporary media.

Never modifies real users, db.sqlite3 or clinical images. No Redis/Docker.
This checks software integration, NOT clinical performance.
"""
import io
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
import time
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neorx.settings')
from dotenv import load_dotenv
load_dotenv(ROOT / 'backend' / '.env')


def require(response, status):
    assert response.status_code == status, (response.status_code, getattr(response, 'data', None))
    return getattr(response, 'data', None)


def main():
    import django
    from django.conf import settings
    settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
    settings.NEORX_INFERENCE_MODE = 'inline'
    settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
    settings.SECURE_SSL_REDIRECT = False
    settings.RATELIMIT_ENABLE = False
    settings.PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    django.setup()
    from django.core.management import call_command
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.contrib.auth import get_user_model
    from django.db import connections
    from rest_framework.test import APIClient
    from diagnostico.services import DetectorTorax
    from estudios.models import ImagenDICOM
    import numpy as np
    import pydicom
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, DigitalXRayImageStorageForPresentation, generate_uid

    checkpoint = os.environ.get('NEORX_MODEL_PATH')
    if checkpoint:
        assert Path(checkpoint).is_file(), 'Configure un checkpoint local.'
    else:
        import torchxrayvision as xrv
        name = os.environ.get('NEORX_BASELINE_WEIGHTS', 'resnet50-res512-all')
        filename = xrv.models.model_urls[name]['weights_url'].rsplit('/', 1)[-1]
        cache = Path(os.environ.get('NEORX_MODEL_CACHE', ROOT / 'backend/models'))
        assert (cache / filename).is_file(), 'Faltan los pesos locales; esta prueba no descarga modelos.'
    scratch = ROOT / '.preflight-temp'
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='neorx-smoke-', dir=scratch) as media:
        settings.MEDIA_ROOT = media
        call_command('migrate', verbosity=0, interactive=False)
        password = secrets.token_urlsafe(24)
        get_user_model().objects.create_user(username='smoke_medico', password=password, rol='medico')
        client, anonymous = APIClient(), APIClient()
        pair = require(client.post('/api/token/', {'username': 'smoke_medico', 'password': password}), 200)
        client.credentials(HTTP_AUTHORIZATION='Bearer ' + pair['access'])
        patient = require(client.post('/api/pacientes/', {
            'nombres': 'Prueba sintética', 'apellidos': 'Sin valor clínico', 'ci': 'SMOKE-LOCAL',
            'fecha_nacimiento': '1990-01-01', 'genero': 'M',
        }), 201)
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = DigitalXRayImageStorageForPresentation
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
        ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
        ds.Modality, ds.BodyPartExamined, ds.ViewPosition = 'DX', 'CHEST', 'PA'
        ds.Rows = ds.Columns = 512
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, 'MONOCHROME2'
        ds.BitsAllocated = ds.BitsStored = 8
        ds.HighBit, ds.PixelRepresentation = 7, 0
        ds.PixelData = np.random.default_rng(23).integers(0, 256, (512, 512), dtype=np.uint8).tobytes()
        buffer = io.BytesIO()
        ds.save_as(buffer, enforce_file_format=True)
        start = time.perf_counter()
        result = require(client.post('/api/estudios/upload/', {
            'archivo': SimpleUploadedFile('sintetico.dcm', buffer.getvalue(), 'application/dicom'),
            'paciente_id': patient['id'],
        }, format='multipart'), 200)
        assert result['status'] == 'SUCCESS', result
        elapsed = round(time.perf_counter() - start, 3)
        image = ImagenDICOM.objects.get(pk=result['imagen_id'])
        preview_path = urlsplit(result['imagen_png_url']).path
        response = client.get(preview_path)
        require(response, 200)
        assert b''.join(response.streaming_content).startswith(b'\x89PNG')
        assert anonymous.get(preview_path).status_code in (401, 403)
        stored = require(client.get(f'/api/diagnostico/resultado/{image.pk}/'), 200)
        assert stored['categoria'] == result['categoria']
        pathology = next(iter(DetectorTorax._modelo.pathologies))
        cam = require(client.get('/api/diagnostico/gradcam/', {'imagen_id': image.pk, 'pathology': pathology}), 200)
        assert cam['overlay'] and cam['solo_calor']
        cached = require(client.get('/api/diagnostico/gradcam/', {'imagen_id': image.pk, 'pathology': pathology}), 200)
        assert cached['cache'] is True
        report_url = f"/api/informes/{result['informe_id']}/"
        report = require(client.get(report_url), 200)
        assert report['imagen_origen'] == image.pk and report['imagen_png_url']
        require(client.patch(report_url, {'estado': 'firmado'}), 400)
        require(client.patch(report_url, {
            'estado': 'revisado', 'tecnica': 'Prueba sintética; sin uso clínico.',
            'hallazgos': 'Datos sintéticos para verificar integración.',
            'correlacion_clinica': 'No corresponde a un paciente real.',
            'impresion': 'Prueba de software, no diagnóstico.',
            'recomendaciones': 'No utilizar con fines clínicos.',
        }), 200)
        require(client.patch(report_url, {'estado': 'firmado'}), 200)
        require(client.patch(report_url, {'hallazgos': 'No debe modificarse'}), 400)
        for suffix, signature in [('pdf/', b'%PDF'), ('dicom-sr/', None)]:
            response = client.get(report_url + suffix)
            require(response, 200)
            content = b''.join(response.streaming_content) if response.streaming else response.content
            if signature:
                assert content.startswith(signature)
            else:
                sr = pydicom.dcmread(io.BytesIO(content))
                # The export intentionally does not assert DICOM verification.
                assert sr.Modality == 'SR' and sr.CompletionFlag == 'COMPLETE'
                assert sr.VerificationFlag == 'UNVERIFIED'
        require(client.get('/api/workspace/resumen/'), 200)
        require(client.post('/api/token/logout/', {'refresh': pair['refresh']}), 200)
        require(anonymous.post('/api/token/refresh/', {'refresh': pair['refresh']}), 401)
        print(json.dumps({
            'result': 'PASS', 'database': 'isolated in-memory', 'input': 'synthetic DICOM (NOT clinical validation)',
            'model': DetectorTorax._model_name, 'classes': list(DetectorTorax._modelo.pathologies),
            'enabled_decisions': [key for key, value in (DetectorTorax._decision_policy or {}).items() if value.get('enabled')],
            'upload_and_cold_inference_seconds': elapsed,
            'gradcam_ms': cam['tiempo_generacion_ms'], 'gradcam_cached': cached['cache'],
            'flows': ['JWT', 'patient', 'upload', 'real CNN', 'private PNG', 'Grad-CAM', 'draft/review/sign', 'PDF', 'DICOM SR', 'dashboard', 'logout'],
        }, indent=2, ensure_ascii=False), flush=True)
        connections.close_all()


if __name__ == '__main__':
    main()
