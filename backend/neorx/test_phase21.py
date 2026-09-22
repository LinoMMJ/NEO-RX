"""API regression tests; all CNN calls use mocks, never clinical evidence."""
import io
import hashlib
from datetime import timedelta
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import CustomUser
from informes.models import InformePreliminar
from neorx.models import AuditLog, log_audit
from estudios.validators import validate_file_comprehensive

pytestmark = pytest.mark.django_db

@pytest.fixture(autouse=True)
def no_rate_limit(settings):
    settings.RATELIMIT_ENABLE = False


def test_jwt_login_logout_and_reuse(medico_user):
    client = APIClient()
    response = client.post('/api/token/', {'username': medico_user.username, 'password': 'medico123'})
    assert response.status_code == 200
    pair = response.data
    client.credentials(HTTP_AUTHORIZATION='Bearer ' + pair['access'])
    assert client.get('/api/informes/').status_code == 200
    assert client.post('/api/token/logout/', {'refresh': pair['refresh']}).status_code == 200
    assert client.post('/api/token/refresh/', {'refresh': pair['refresh']}).status_code == 401
    assert AuditLog.objects.filter(action='login').exists()
    assert AuditLog.objects.filter(action='logout').exists()


def test_logout_token_ownership(auth_medico, admin_user):
    token = str(RefreshToken.for_user(admin_user))
    assert auth_medico.post('/api/token/logout/', {'refresh': token}).status_code == 400
    assert RefreshToken(token)


def test_revoke_all_refresh(auth_medico, medico_user):
    tokens = [str(RefreshToken.for_user(medico_user)) for _ in range(2)]
    assert auth_medico.post('/api/token/revoke/').status_code == 200
    client = APIClient()
    for token in tokens:
        assert client.post('/api/token/refresh/', {'refresh': token}).status_code == 401


def test_failed_login_audited(api_client):
    assert api_client.post('/api/token/', {'username': 'missing', 'password': 'invalid'}).status_code == 401
    assert AuditLog.objects.filter(action='login_failed').exists()


@pytest.mark.parametrize('role', ['recepcionista', 'administrador'])
@pytest.mark.parametrize('method', ['put', 'patch'])
def test_nonmedical_cannot_change_report(role, method, imagen_con_resultado):
    user = CustomUser.objects.create_user(username='denied', password='test-pass', rol=role)
    client = APIClient(); client.force_authenticate(user)
    report = InformePreliminar.objects.create(estudio=imagen_con_resultado.estudio)
    assert getattr(client, method)(f'/api/informes/{report.pk}/', {'estado': 'firmado'}, format='json').status_code == 403
    assert client.post('/api/informes/generar/', {'estudio_id': report.estudio_id}).status_code == 403
    report.refresh_from_db(); assert report.estado == 'borrador'


def test_review_sign_immutable_and_no_regeneration(auth_medico, imagen_con_resultado):
    response = auth_medico.post('/api/informes/generar/', {'estudio_id': imagen_con_resultado.estudio_id})
    assert response.status_code == 200
    pk = response.data['id']; url = f'/api/informes/{pk}/'
    assert auth_medico.patch(url, {'estado': 'firmado'}).status_code == 400
    assert auth_medico.patch(url, {'estado': 'revisado', 'hallazgos': 'Revisión profesional'}).status_code == 200
    assert auth_medico.patch(url, {'estado': 'firmado'}).status_code == 200
    assert auth_medico.patch(url, {'hallazgos': 'Manipulado'}).status_code == 400
    assert auth_medico.post('/api/informes/generar/', {'estudio_id': imagen_con_resultado.estudio_id}).data['hallazgos'] == 'Revisión profesional'
    imagen_con_resultado.estudio.refresh_from_db()
    assert imagen_con_resultado.estudio.estado == 'completado'


@pytest.mark.parametrize('role', ['medico', 'recepcionista'])
def test_users_rbac(role):
    user = CustomUser.objects.create_user(username='nonadmin', password='test-pass', rol=role)
    client=APIClient(); client.force_authenticate(user)
    assert client.get('/api/admin/users/').status_code == 403
    assert client.post('/api/admin/users/', {'username': 'escalated', 'rol': 'administrador'}).status_code == 403


def test_admin_user_crud_password_soft_delete(auth_admin):
    response=auth_admin.post('/api/admin/users/', {'username': 'created', 'password': 'Strong-new-phrase-728!',
        'rol': 'recepcionista', 'is_superuser': True, 'is_staff': True}, format='json')
    assert response.status_code == 201
    user=CustomUser.objects.get(pk=response.data['id'])
    assert not user.is_superuser and not user.is_staff
    assert user.check_password('Strong-new-phrase-728!') and 'password' not in response.data
    assert auth_admin.get('/api/admin/users/?search=created&rol=recepcionista&page_size=5').data['count'] == 1
    assert auth_admin.patch(f'/api/admin/users/{user.pk}/', {'password': 'Other-strong-phrase-452!', 'rol':'medico'}).status_code == 200
    user.refresh_from_db(); assert user.check_password('Other-strong-phrase-452!')
    assert auth_admin.post(f'/api/admin/users/{user.pk}/reset_password/').status_code == 200
    assert auth_admin.delete(f'/api/admin/users/{user.pk}/').status_code == 204
    user.refresh_from_db(); assert not user.is_active
    assert auth_admin.post(f'/api/admin/users/{user.pk}/toggle_active/').data['is_active']


def test_password_reset_secure_single_use(api_client, medico_user, mailoutbox, capsys):
    import re
    token_before = str(RefreshToken.for_user(medico_user))
    found=api_client.post('/api/password/reset/', {'email': medico_user.email})
    missing=api_client.post('/api/password/reset/', {'email':'nobody@example.test'})
    assert found.status_code == 200 and missing.status_code == 404
    assert len(mailoutbox)==1
    code=re.search(r'código de recuperación es: (\d{6})', mailoutbox[0].body).group(1)
    medico_user.refresh_from_db()
    assert medico_user.password_reset_token and medico_user.password_reset_token != code
    assert code not in capsys.readouterr().out
    assert api_client.post('/api/password/reset/confirm/', {'email':medico_user.email,'reset_proof':code,'new_password':'Secure-new-phrase-348!'}).status_code == 400
    verified=api_client.post('/api/password/reset/verify/', {'email':medico_user.email,'code':code})
    assert verified.status_code == 200
    proof=verified.data['reset_proof']
    assert api_client.post('/api/password/reset/confirm/', {'email':medico_user.email,'reset_proof':proof,'new_password':'short'}).status_code == 400
    assert api_client.post('/api/password/reset/confirm/', {'email':medico_user.email,'reset_proof':proof,'new_password':'Secure-new-phrase-348!'}).status_code == 200
    assert api_client.post('/api/password/reset/confirm/', {'email':medico_user.email,'reset_proof':proof,'new_password':'Secure-new-phrase-348!'}).status_code == 400
    assert api_client.post('/api/token/refresh/', {'refresh':token_before}).status_code == 401
    medico_user.refresh_from_db(); assert medico_user.check_password('Secure-new-phrase-348!')
    assert AuditLog.objects.filter(resource_type='password_reset').exists()


def test_expired_reset(api_client, medico_user):
    from accounts.views import _reset_digest
    medico_user.password_reset_token=_reset_digest(medico_user,'123456')
    medico_user.password_reset_expires=timezone.now()-timedelta(seconds=1)
    medico_user.save()
    assert api_client.post('/api/password/reset/verify/', {'email':medico_user.email,'code':'123456'}).status_code == 400


def test_audit_redacts_secrets():
    log_audit(None, action='update',resource_type='unit',metadata={'refresh_token':'sensitive','nested':{'password':'sensitive'}})
    assert AuditLog.objects.get(resource_type='unit').metadata == {'refresh_token':'[REDACTED]', 'nested': {'password':'[REDACTED]'}}


@pytest.mark.parametrize('url', ['/api/pacientes/', '/api/pacientes/estudios/', '/api/estudios/imagenes/', '/api/informes/', '/api/metrics/operacionales/'])
def test_critical_lists_authenticated(url, auth_medico, api_client):
    assert APIClient().get(url).status_code == 401
    response=auth_medico.get(url, {'search':'Fixture', 'ordering':'-id'})
    assert response.status_code == 200


@pytest.mark.parametrize('query', ['', '?dias=1', '?fecha_desde=2020-01-01&fecha_hasta=2020-01-02'])
def test_dashboard_sqlite_empty_and_data(query, auth_medico, imagen_con_resultado, medico_user):
    url='/api/metrics/operacionales/'+query
    assert auth_medico.get(url).status_code==200
    InformePreliminar.objects.create(estudio=imagen_con_resultado.estudio, estado='firmado',medico=medico_user,fecha_firmado=timezone.now())
    response=auth_medico.get(url); assert response.status_code==200
    assert response.data['metricas_cnn']['estado']=='pendiente'
    if not query:
        assert response.data['completitud']['completados']==1
        assert response.data['latencia_diagnostico']['muestras']==1


@pytest.mark.parametrize('query',['dias=abc','dias=0','dias=999999','fecha_desde=bad','fecha_desde=2025-01-01&fecha_hasta=2020-01-01'])
def test_dashboard_bad_ranges(query, auth_medico):
    assert auth_medico.get('/api/metrics/operacionales/?'+query).status_code==400


def png_bytes():
    buf=io.BytesIO(); Image.fromarray(np.zeros((64,64),dtype=np.uint8)).save(buf, format='PNG');return buf.getvalue()


@pytest.mark.parametrize('name,content', [('empty.png',b''),('corrupt.png',b'corrupt'),('false.dcm',png_bytes()),('false.jpg',png_bytes()),('invalid.dcm',b'invalid DICOM')])
def test_invalid_upload_content(name,content):
    assert not validate_file_comprehensive(SimpleUploadedFile(name,content))['valid']


def test_valid_png_and_size(settings):
    assert validate_file_comprehensive(SimpleUploadedFile('valid.png',png_bytes(),content_type='text/plain'))['valid']
    settings.IMAGE_MAX_FILE_SIZE=10
    assert not validate_file_comprehensive(SimpleUploadedFile('large.png',png_bytes()))['valid']


def dicom_bytes():
    from pydicom.dataset import FileDataset, FileMetaDataset
    from pydicom.uid import ExplicitVRLittleEndian, DigitalXRayImageStorageForPresentation, generate_uid
    meta=FileMetaDataset(); meta.TransferSyntaxUID=ExplicitVRLittleEndian
    meta.MediaStorageSOPClassUID=DigitalXRayImageStorageForPresentation;meta.MediaStorageSOPInstanceUID=generate_uid()
    ds=FileDataset(None, {}, file_meta=meta, preamble=b'\0'*128)
    ds.SOPClassUID=meta.MediaStorageSOPClassUID;ds.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
    ds.StudyInstanceUID=generate_uid();ds.Modality='DX';ds.PatientID='SYNTHETIC';ds.PatientName='Unit^Fixture'
    ds.Rows=64;ds.Columns=64;ds.SamplesPerPixel=1;ds.PhotometricInterpretation='MONOCHROME2'
    ds.BitsAllocated=8;ds.BitsStored=8;ds.HighBit=7;ds.PixelRepresentation=0
    ds.PixelData=np.zeros((64,64),dtype=np.uint8).tobytes()
    buf=io.BytesIO();ds.save_as(buf,enforce_file_format=True);return buf.getvalue()


def test_valid_dicom_metadata():
    result=validate_file_comprehensive(SimpleUploadedFile('synthetic.dcm',dicom_bytes()))
    assert result['valid'] and result['metadata']['Modality']=='DX' and result['metadata']['Rows']==64


def test_reception_upload_repetition(auth_recepcionista, imagen_dicom, settings, tmp_path):
    settings.MEDIA_ROOT=tmp_path
    response=auth_recepcionista.post('/api/estudios/upload/',{'estudio_id':imagen_dicom.estudio_id,'archivo':SimpleUploadedFile('valid.png',png_bytes())})
    assert response.status_code==200 and response.data['alerta']=='borrosidad'
    imagen_dicom.estudio.refresh_from_db();assert imagen_dicom.estudio.estado=='requiere_repeticion'
    assert AuditLog.objects.filter(resource_type='estudio',action='validate').exists()


@pytest.mark.parametrize('role',['administrador'])
def test_upload_rbac(role, imagen_dicom):
    user=CustomUser.objects.create_user(username='blocked-upload',password='test-pass',rol=role)
    client=APIClient();client.force_authenticate(user)
    assert client.post('/api/estudios/upload/',{'estudio_id':imagen_dicom.estudio_id,'archivo':SimpleUploadedFile('valid.png',png_bytes())}).status_code==403


def test_structured_results_draft(auth_medico, imagen_con_resultado):
    result=imagen_con_resultado.resultado_cnn
    result.patologias={'hallazgos':[{'etiqueta':'Neumonía','probabilidad_estimada':0.8}], 'probabilidades':{'Pneumonia':0.8}}
    result.save()
    response=auth_medico.post('/api/informes/generar/',{'estudio_id':imagen_con_resultado.estudio_id})
    assert response.status_code==200 and 'Neumonía' in response.data['hallazgos']
    assert response.data['probabilidades']=={'Neumonía':0.8}
    assert 'Silueta cardíaca' not in response.data['hallazgos']


@pytest.mark.parametrize('name,content', [('empty.png', b''), ('corrupt.png', b'corrupt'), ('fake.dcm', png_bytes())])
def test_invalid_file_endpoint(name, content, auth_recepcionista, imagen_dicom, settings, tmp_path):
    from estudios.models import ImagenDICOM
    settings.MEDIA_ROOT=tmp_path
    before=ImagenDICOM.objects.count()
    response=auth_recepcionista.post('/api/estudios/upload/', {'estudio_id':imagen_dicom.estudio_id,
        'archivo':SimpleUploadedFile(name,content)})
    assert response.status_code == 400 and ImagenDICOM.objects.count()==before


def test_dicom_upload_technical_quality(auth_recepcionista, imagen_dicom, settings, tmp_path):
    settings.MEDIA_ROOT=tmp_path
    response=auth_recepcionista.post('/api/estudios/upload/', {'estudio_id':imagen_dicom.estudio_id,
        'archivo':SimpleUploadedFile('synthetic.dcm',dicom_bytes())})
    assert response.status_code==200 and response.data['alerta']=='borrosidad'
    from estudios.models import ImagenDICOM
    image=ImagenDICOM.objects.get(pk=response.data['imagen_id'])
    assert image.es_nitida is False and image.varianza_laplaciana==0 and image.archivo_png


def test_upload_dispatches_once(auth_recepcionista, imagen_dicom, settings, tmp_path):
    from types import SimpleNamespace
    settings.MEDIA_ROOT=tmp_path
    with patch('estudios.views.calcular_borrosidad',return_value=(True,150)), patch('diagnostico.tasks.procesar_imagen_cnn.delay',return_value=SimpleNamespace(id='mock-task')) as delay:
        response=auth_recepcionista.post('/api/estudios/upload/',{'estudio_id':imagen_dicom.estudio_id,
            'archivo':SimpleUploadedFile('valid.png',png_bytes())})
    assert response.status_code==202 and response.data['task_id']=='mock-task'
    assert delay.call_count==1


def test_cnn_task_is_routed_to_worker_queue(settings):
    route = settings.CELERY_TASK_ROUTES['diagnostico.tasks.procesar_imagen_cnn']
    assert route['queue'] == 'cnn_inference'
    assert route['routing_key'] == 'cnn_inference'


def test_checkpoint_missing_is_unit_error(monkeypatch, tmp_path):
    from diagnostico.services import DetectorTorax
    monkeypatch.setenv('NEORX_MODEL_PATH',str(tmp_path/'absent.pt'))
    with pytest.raises((RuntimeError, FileNotFoundError)):
        DetectorTorax.cargar()


def test_signed_records_cannot_be_deleted(auth_admin, imagen_con_resultado, medico_user):
    report=InformePreliminar.objects.create(estudio=imagen_con_resultado.estudio,estado='firmado',medico=medico_user,fecha_firmado=timezone.now())
    assert auth_admin.delete(f'/api/pacientes/estudios/{report.estudio_id}/').status_code==400
    assert auth_admin.delete(f'/api/pacientes/{report.estudio.paciente_id}/').status_code==400
    assert InformePreliminar.objects.filter(pk=report.pk).exists()


def test_not_found_and_validation_errors(auth_medico, auth_admin):
    assert auth_medico.get('/api/informes/999999/').status_code==404
    response=auth_admin.post('/api/admin/users/',{'username':'weak','password':'x','rol':'tecnico'})
    assert response.status_code==400 and response.data['status']==400 and 'errors' in response.data



def test_async_result_adapter_and_audit(imagen_dicom):
    from diagnostico.tasks import procesar_imagen_cnn
    from diagnostico.models import ResultadoCNN
    payload={'hallazgos':[{'etiqueta':'Neumonía','probabilidad_estimada':0.8}]}
    with patch('diagnostico.tasks.DetectorTorax.desde_dicom', return_value=payload):
        response=procesar_imagen_cnn.run(imagen_dicom.pk)
    assert response['patologias']=={'Neumonía':0.8}
    assert ResultadoCNN.objects.get(imagen=imagen_dicom).patologias=={'Neumonía':0.8}
    assert AuditLog.objects.filter(resource_type='resultado_cnn',action='process').exists()


def test_password_reset_rejects_old_access(api_client, medico_user, mailoutbox):
    import re
    refresh=RefreshToken.for_user(medico_user)
    old_access=str(refresh.access_token)
    api_client.post('/api/password/reset/', {'email':medico_user.email})
    code=re.search(r'código de recuperación es: (\d{6})', mailoutbox[0].body).group(1)
    proof=api_client.post('/api/password/reset/verify/', {'email':medico_user.email,'code':code}).data['reset_proof']
    assert api_client.post('/api/password/reset/confirm/', {'email':medico_user.email,'reset_proof':proof,'new_password':'Secure-access-phrase-683!'}).status_code==200
    api_client.credentials(HTTP_AUTHORIZATION='Bearer '+old_access)
    assert api_client.get('/api/informes/').status_code==401


def test_medico_can_reach_upload_validation(imagen_dicom):
    user=CustomUser.objects.create_user(username='clinical-upload',password='test-pass',rol='medico')
    client=APIClient();client.force_authenticate(user)
    response=client.post('/api/estudios/upload/',{'estudio_id':imagen_dicom.estudio_id,'archivo':SimpleUploadedFile('invalid.png',b'invalid')})
    assert response.status_code==400
