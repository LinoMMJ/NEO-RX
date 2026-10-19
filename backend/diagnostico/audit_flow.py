"""Exercise the real checkpoint/API against a disposable database and media.

Run from backend: python -m diagnostico.audit_flow [--serve]
--serve exposes only the disposable fixture at 127.0.0.1:8001 for UI checks.
No existing clinical database records are read or changed.
"""
import argparse
import io
import json
import logging
import os
from pathlib import Path
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('--image', type=Path)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    source = args.image or next(Path('media').rglob('*.jpg'), None)
    if source is None:
        parser.error('Provide --image with a local radiograph.')
    source = source.resolve()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'neorx.settings')
    from django.conf import settings
    from django.core.management import call_command
    import django

    with tempfile.TemporaryDirectory(prefix='neorx-audit-') as folder:
        settings.DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': str(Path(folder) / 'audit.sqlite3')}}
        settings.MEDIA_ROOT = str(Path(folder) / 'media')
        settings.ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
        settings.CORS_ALLOWED_ORIGINS = ['http://127.0.0.1:5174', 'http://localhost:5174']
        settings.NEORX_INFERENCE_MODE = 'inline'
        settings.DEBUG = True
        settings.SECURE_SSL_REDIRECT = False
        settings.RATELIMIT_ENABLE = False
        django.setup()
        logging.disable(logging.WARNING)
        call_command('migrate', verbosity=0)
        from accounts.models import CustomUser
        from rest_framework.test import APIClient
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import numpy as np
        from pydicom.dataset import FileDataset, FileMetaDataset
        from pydicom.uid import ExplicitVRLittleEndian, DigitalXRayImageStorageForPresentation, generate_uid
        from .services import DetectorTorax

        user = CustomUser.objects.create_user(username='audit_medico', password='Local-Audit-Only-729!', rol='medico', first_name='Prueba', last_name='Local')
        client = APIClient()
        login = client.post('/api/token/', {'username': user.username, 'password': 'Local-Audit-Only-729!'})
        assert login.status_code == 200, login.data
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
        patient = client.post('/api/pacientes/', {'nombres': 'Paciente', 'apellidos': 'Prueba técnica', 'ci': 'AUDIT-2026', 'fecha_nacimiento': '1980-01-01', 'genero': 'M'})
        assert patient.status_code == 201, patient.data
        patient_id = patient.data['id']
        started = time.perf_counter()
        DetectorTorax.cargar()
        results = {'model_load_seconds': round(time.perf_counter() - started, 3), 'flows': []}

        with Image.open(source) as image:
            pixels = np.asarray(image.convert('L'))
        meta = FileMetaDataset()
        meta.TransferSyntaxUID = ExplicitVRLittleEndian
        meta.MediaStorageSOPClassUID = DigitalXRayImageStorageForPresentation
        meta.MediaStorageSOPInstanceUID = generate_uid()
        ds = FileDataset(None, {}, file_meta=meta, preamble=b'\0' * 128)
        ds.SOPClassUID, ds.SOPInstanceUID = meta.MediaStorageSOPClassUID, meta.MediaStorageSOPInstanceUID
        ds.Modality, ds.BodyPartExamined, ds.ViewPosition = 'DX', 'CHEST', 'PA'
        ds.Rows, ds.Columns = pixels.shape
        ds.SamplesPerPixel, ds.PhotometricInterpretation = 1, 'MONOCHROME2'
        ds.BitsAllocated = ds.BitsStored = 8
        ds.HighBit, ds.PixelRepresentation = 7, 0
        ds.PixelData = pixels.tobytes()
        buffer = io.BytesIO()
        ds.save_as(buffer, enforce_file_format=True)
        dicom = buffer.getvalue()
        preview = client.post('/api/estudios/vista-previa/', {'archivo': SimpleUploadedFile('audit.dcm', dicom)}, format='multipart')
        assert preview.status_code == 200 and preview.data['preview_url'].startswith('data:image/png;'), preview.data

        for name, content in [('audit.jpg', source.read_bytes()), ('audit.dcm', dicom)]:
            started = time.perf_counter()
            response = client.post('/api/estudios/upload/', {'archivo': SimpleUploadedFile(name, content), 'paciente_id': patient_id}, format='multipart')
            duration = time.perf_counter() - started
            assert response.status_code == 200 and response.data.get('status') == 'SUCCESS', response.data
            payload = response.data
            image_id, report_id = payload['imagen_id'], payload['informe_id']
            detail = client.get(f'/api/diagnostico/resultado/{image_id}/')
            assert detail.status_code == 200 and len(detail.data['hallazgos']) == 12
            scores = detail.data['patologias']
            assert all(0 <= value <= 1 for value in scores.values())
            maps = []
            for pathology in ('Pneumonia', 'Mass', 'Pneumonia'):
                start = time.perf_counter()
                cam = client.get('/api/diagnostico/gradcam/', {'imagen_id': image_id, 'pathology': pathology})
                assert cam.status_code == 200, cam.data
                assert cam.data['overlay'].startswith('data:image/png;')
                maps.append({'seconds': round(time.perf_counter() - start, 3), 'cached': cam.data['cache']})
            report = client.get(f'/api/informes/{report_id}/')
            assert report.data['imagen_png_url'] and report.data['imagen_origen'] == image_id
            from urllib.parse import urlsplit
            image_response = client.get(urlsplit(report.data['imagen_png_url']).path)
            assert image_response.status_code == 200
            image_response.close()
            fields = {'tecnica': 'Prueba técnica con imagen de referencia.', 'hallazgos': 'Contenido sintético para verificar el formulario.',
                      'correlacion_clinica': 'Prueba de software sin interpretación clínica.', 'impresion': 'Documento de prueba técnica.',
                      'recomendaciones': 'No utilizar este documento como informe clínico.', 'estado': 'revisado'}
            assert client.patch(f'/api/informes/{report_id}/', fields).status_code == 200
            assert client.patch(f'/api/informes/{report_id}/', {'estado': 'firmado'}).status_code == 200
            pdf = client.get(f'/api/informes/{report_id}/pdf/')
            assert pdf.status_code == 200, getattr(pdf, 'data', None)
            pdf_data = b''.join(pdf.streaming_content) if pdf.streaming else pdf.content
            assert pdf_data.startswith(b'%PDF')
            results['flows'].append({'format': Path(name).suffix, 'upload_seconds': round(duration, 3),
                                     'inference_seconds': payload['tiempo_inferencia_seg'], 'gradcam': maps,
                                     'report_image': 'OK', 'signed_pdf_bytes': len(pdf_data), 'classes': len(scores)})
        output = Path('../docs/auditoria-flujo-2026-10-14.json')
        output.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(json.dumps(results, indent=2), flush=True)
        if args.serve:
            print('Servidor de pruebas temporal en http://127.0.0.1:8001', flush=True)
            call_command('runserver', '127.0.0.1:8001', use_reloader=False, verbosity=0)


if __name__ == '__main__':
    main()
