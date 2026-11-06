"""Regression checks for the local final-review workflow (no Redis or Docker)."""
from concurrent.futures import Future
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.django_db
@pytest.mark.parametrize("query", [
    "paciente=abc", "estudio=abc", "paciente=-1", "fecha_desde=no-fecha",
    "fecha_hasta=2026-02-30", "fecha_desde=2026-10-23&fecha_hasta=2026-10-01",
])
def test_image_list_rejects_invalid_filters(auth_medico, query):
    assert auth_medico.get(f"/api/estudios/imagenes/?{query}").status_code == 400


@pytest.mark.django_db
def test_upload_rejects_invalid_study_identifier(auth_medico):
    response = auth_medico.post('/api/estudios/upload/', {
        'archivo': SimpleUploadedFile('x.png', b'not needed for id validation'),
        'estudio_id': 'invalid',
    }, format='multipart')
    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_task_does_not_contact_redis(auth_medico):
    with patch('celery.result.AsyncResult') as result:
        response = auth_medico.get('/api/estudios/tarea/invalid/')
    assert response.status_code == 400
    result.assert_not_called()


def test_local_queue_deduplicates_in_flight_image():
    from diagnostico import local_queue
    future = Future()
    with patch.object(local_queue, '_pending', set()), patch.object(local_queue._executor, 'submit', return_value=future) as submit:
        assert local_queue.enqueue_local_inference(23) == 'local-23'
        assert local_queue.enqueue_local_inference(23) == 'local-23'
        submit.assert_called_once()
        future.set_result(None)
        assert 23 not in local_queue._pending
        local_queue.enqueue_local_inference(23)
        assert submit.call_count == 2


def test_local_queue_submit_failure_allows_retry():
    from diagnostico import local_queue
    with patch.object(local_queue, '_pending', set()), patch.object(local_queue._executor, 'submit', side_effect=RuntimeError('closed')):
        with pytest.raises(RuntimeError):
            local_queue.enqueue_local_inference(23)
        assert not local_queue._pending


@pytest.mark.django_db
def test_failed_draft_does_not_publish_partial_result(imagen_dicom, auth_medico):
    from diagnostico.tasks import procesar_imagen_cnn
    from diagnostico.models import ResultadoCNN
    imagen_dicom.estado_procesamiento = 'pendiente'
    imagen_dicom.save()
    with patch('diagnostico.services.DetectorTorax.desde_dicom', return_value={'hallazgos': []}), patch('informes.services.create_ai_draft_report', side_effect=RuntimeError('draft failed')):
        with pytest.raises(RuntimeError):
            procesar_imagen_cnn.run(imagen_dicom.pk)
    imagen_dicom.refresh_from_db()
    assert imagen_dicom.estado_procesamiento == 'error'
    assert not ResultadoCNN.objects.filter(imagen=imagen_dicom).exists()
    assert auth_medico.get(f'/api/estudios/tarea/local-{imagen_dicom.pk}/').data['status'] == 'FAILURE'


@pytest.mark.django_db
def test_background_success_includes_report_and_category(imagen_dicom, auth_medico):
    from diagnostico.tasks import procesar_imagen_cnn
    imagen_dicom.estado_procesamiento = 'pendiente'
    imagen_dicom.save()
    payload = {'hallazgos': [], 'categoria': {'estado': 'no_concluyente', 'clave': None}}
    with patch('diagnostico.services.DetectorTorax.desde_dicom', return_value=payload):
        result = procesar_imagen_cnn.run(imagen_dicom.pk)
    response = auth_medico.get(f'/api/estudios/tarea/local-{imagen_dicom.pk}/')
    assert response.status_code == 200
    assert response.data['status'] == 'SUCCESS'
    assert response.data['informe_id'] == result['informe_id']
    assert response.data['categoria']['estado'] == 'no_concluyente'
    assert response.data['patologias'] == {}
    saved = auth_medico.get(f'/api/diagnostico/resultado/{imagen_dicom.pk}/')
    assert saved.data['categoria'] == payload['categoria']


@pytest.mark.django_db
def test_retry_uses_saved_image_and_does_not_queue_twice(imagen_dicom, auth_medico, settings):
    settings.NEORX_INFERENCE_MODE = 'thread'
    imagen_dicom.estado_procesamiento = 'error'
    imagen_dicom.save()
    url = f'/api/estudios/imagen/{imagen_dicom.pk}/reintentar/'
    with patch.object(imagen_dicom.archivo_dicom.storage, 'exists', return_value=True), patch('diagnostico.local_queue.enqueue_local_inference', return_value=f'local-{imagen_dicom.pk}') as enqueue:
        assert auth_medico.post(url).status_code == 202
        assert auth_medico.post(url).status_code == 409
    enqueue.assert_called_once_with(imagen_dicom.pk)
    imagen_dicom.refresh_from_db()
    assert imagen_dicom.estado_procesamiento == 'pendiente'


@pytest.mark.django_db
def test_retry_rejects_signed_or_unavailable_image(imagen_dicom, auth_medico):
    from informes.models import InformePreliminar
    imagen_dicom.estado_procesamiento = 'error'
    imagen_dicom.save()
    url = f'/api/estudios/imagen/{imagen_dicom.pk}/reintentar/'
    with patch('diagnostico.local_queue.enqueue_local_inference') as enqueue:
        assert auth_medico.post(url).status_code == 409  # absent original
        InformePreliminar.objects.create(estudio=imagen_dicom.estudio, estado='firmado')
        assert auth_medico.post(url).status_code == 409
    enqueue.assert_not_called()


@pytest.mark.django_db
def test_retry_is_not_available_to_admin_or_anonymous(imagen_dicom, auth_admin, api_client):
    from rest_framework.test import APIClient
    url = f'/api/estudios/imagen/{imagen_dicom.pk}/reintentar/'
    assert auth_admin.post(url).status_code == 403
    assert APIClient().post(url).status_code == 401


@pytest.mark.django_db(transaction=True)
def test_real_local_worker_finishes_saved_image(imagen_dicom):
    import time
    from diagnostico.local_queue import enqueue_local_inference
    imagen_dicom.estado_procesamiento = 'pendiente'
    imagen_dicom.save()
    with patch('diagnostico.services.DetectorTorax.desde_dicom', return_value={'hallazgos': []}):
        assert enqueue_local_inference(imagen_dicom.pk) == f'local-{imagen_dicom.pk}'
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            imagen_dicom.refresh_from_db()
            if imagen_dicom.estado_procesamiento in {'procesado', 'error'}:
                break
            time.sleep(0.05)
    assert imagen_dicom.estado_procesamiento == 'procesado'
    assert imagen_dicom.estudio.informe.pk
