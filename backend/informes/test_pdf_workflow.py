from io import BytesIO
from pathlib import Path

import pytest
from django.core.files.base import ContentFile
from PIL import Image
from pypdf import PdfReader

from informes.models import InformePreliminar

pytestmark = pytest.mark.django_db


def report(imagen):
    return InformePreliminar.objects.create(
        estudio=imagen.estudio, imagen_origen=imagen,
        tecnica='Radiografía de prueba.', hallazgos='Hallazgo sintético para verificar exportación.',
        correlacion_clinica='Datos de prueba.', impresion='Pendiente de revisión.',
        recomendaciones='Revisar el estudio original.',
    )


def read_pdf(response):
    assert response.status_code == 200
    data = b''.join(response.streaming_content)
    reader = PdfReader(BytesIO(data))
    return data, reader, '\n'.join(page.extract_text() for page in reader.pages)


def test_draft_pdf_contains_source_image_and_never_signs(auth_medico, imagen_con_resultado, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    png = BytesIO()
    Image.new('RGB', (320, 480), '#606060').save(png, format='PNG')
    imagen_con_resultado.archivo_png.save('source.png', ContentFile(png.getvalue()))
    draft = report(imagen_con_resultado)
    url = f'/api/informes/{draft.pk}/pdf/'
    assert auth_medico.get(url).status_code == 400
    response = auth_medico.get(url, {'borrador': 1})
    data, reader, text = read_pdf(response)
    assert 'PREINFORME NO FIRMADO' in text
    assert 'Documento sin firma médica' in text
    assert 'IMAGEN DEL ESTUDIO' in text
    assert sum(len(page.images) for page in reader.pages) == 1
    assert all('PREINFORME NO FIRMADO' in page.extract_text() for page in reader.pages)
    draft.refresh_from_db()
    assert draft.estado == 'borrador' and draft.fecha_firmado is None
    assert {'private', 'no-store'} <= set(response['Cache-Control'].split(', '))
    output = Path(__file__).resolve().parents[2] / 'tmp/access-pdf-20261027'
    output.mkdir(parents=True, exist_ok=True)
    (output / 'preinforme-sintetico.pdf').write_bytes(data)


def test_draft_pdf_access_is_restricted(auth_recepcionista, api_client, imagen_con_resultado):
    draft = report(imagen_con_resultado)
    url = f'/api/informes/{draft.pk}/pdf/?borrador=1'
    assert auth_recepcionista.get(url).status_code == 403
    api_client.force_authenticate(user=None)
    assert api_client.get(url).status_code == 401


def test_invalid_signature_cannot_be_bypassed(auth_medico, imagen_con_resultado):
    draft = report(imagen_con_resultado)
    draft.estado = 'firmado'
    draft.save()
    assert auth_medico.get(f'/api/informes/{draft.pk}/pdf/?borrador=1').status_code == 400


def test_pdf_missing_image_and_long_content_are_handled(auth_medico, imagen_con_resultado, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    draft = report(imagen_con_resultado)
    draft.hallazgos = ('Texto largo de prueba para comprobar la paginación.\n' * 160) + 'FIN DEL CONTENIDO'
    draft.save()
    _, reader, text = read_pdf(auth_medico.get(f'/api/informes/{draft.pk}/pdf/?borrador=1'))
    assert len(reader.pages) > 2
    assert 'FIN DEL CONTENIDO' in text
    assert 'Imagen de referencia no disponible' in text


def test_pdf_repairs_absent_preview_from_original(auth_medico, imagen_con_resultado, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    content = BytesIO()
    Image.new('RGB', (128, 256), 'white').save(content, format='TIFF')
    imagen_con_resultado.archivo_png = ''
    imagen_con_resultado.archivo_dicom.save('source.tiff', ContentFile(content.getvalue()))
    draft = report(imagen_con_resultado)
    _, reader, _ = read_pdf(auth_medico.get(f'/api/informes/{draft.pk}/pdf/?borrador=1'))
    assert sum(len(page.images) for page in reader.pages) == 1

@pytest.mark.django_db
def test_review_sign_and_export_complete_workflow(auth_medico, imagen_con_resultado, medico_user):
    draft = report(imagen_con_resultado)
    url = f'/api/informes/{draft.pk}/'
    assert auth_medico.patch(url, {'estado': 'firmado'}, format='json').status_code == 400
    response = auth_medico.patch(url, {'estado': 'revisado', 'tecnica': '  Tecnica verificada  '}, format='json')
    assert response.status_code == 200
    assert response.data['tecnica'] == 'Tecnica verificada'
    signed = auth_medico.patch(url, {'estado': 'firmado'}, format='json')
    assert signed.status_code == 200
    assert signed.data['medico'] == medico_user.pk and signed.data['fecha_firmado']
    _, _, text = read_pdf(auth_medico.get(url + 'pdf/'))
    assert 'PREINFORME NO FIRMADO' not in text
    assert auth_medico.patch(url, {'estado': 'borrador'}, format='json').status_code == 400
