"""Session and form regressions using only synthetic users/patients."""
import pytest
from django.conf import settings
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken
from django.utils import timezone
from datetime import timedelta

pytestmark = pytest.mark.django_db

@pytest.mark.parametrize('remember,hours', [(False, 8), (True, 720)])
def test_login_session_lifetime_and_rotation(api_client, medico_user, remember, hours):
    response = api_client.post('/api/token/', {'username': medico_user.username, 'password': 'medico123', 'remember_me': remember}, format='json')
    assert response.status_code == 200
    refresh = RefreshToken(response.data['refresh']); access = AccessToken(response.data['access'])
    assert hours * 3600 <= refresh['exp'] - refresh['iat'] <= hours * 3600 + 15
    assert access['exp'] - access['iat'] == 15 * 60
    assert refresh['remember_me'] is remember
    deadline = refresh['session_expires_at']
    outstanding = OutstandingToken.objects.get(jti=refresh['jti'])
    assert int(outstanding.expires_at.timestamp()) == deadline
    rotated = api_client.post('/api/token/refresh/', {'refresh': str(refresh)}, format='json')
    assert rotated.status_code == 200
    next_token = RefreshToken(rotated.data['refresh'])
    assert next_token['jti'] != refresh['jti']
    assert next_token['exp'] == next_token['session_expires_at'] == deadline
    assert api_client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code == 401
    assert api_client.post('/api/token/refresh/', {'refresh': str(next_token)}).status_code == 200


def test_absolute_session_deadline_cannot_be_extended(api_client, medico_user):
    refresh = RefreshToken.for_user(medico_user)
    refresh['session_expires_at'] = int(timezone.now().timestamp()) - 1
    assert api_client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code == 401


def test_refresh_rejects_password_change(api_client, medico_user):
    refresh = RefreshToken.for_user(medico_user)
    medico_user.set_password('Updated-strong-password-729!'); medico_user.save()
    assert api_client.post('/api/token/refresh/', {'refresh': str(refresh)}).status_code == 401


def test_refresh_updates_identity_and_rejects_inactive(api_client, medico_user):
    refresh = RefreshToken.for_user(medico_user)
    medico_user.username = 'renamed_unit'; medico_user.rol = 'recepcionista'; medico_user.save()
    result = api_client.post('/api/token/refresh/', {'refresh': str(refresh)})
    assert result.status_code == 200
    access = AccessToken(result.data['access'])
    assert access['username'] == 'renamed_unit' and access['rol'] == 'recepcionista'
    medico_user.is_active = False; medico_user.save()
    assert api_client.post('/api/token/refresh/', {'refresh': result.data['refresh']}).status_code == 401


def test_admin_updates_all_form_fields_without_changing_password(auth_admin, medico_user):
    url = f'/api/admin/users/{medico_user.pk}/'
    response = auth_admin.patch(url, {'username': 'edited_unit', 'first_name': 'Synthetic', 'last_name': 'Edited', 'email': 'edited@example.test', 'rol': 'recepcionista', 'is_active': False}, format='json')
    assert response.status_code == 200
    medico_user.refresh_from_db()
    assert medico_user.username == 'edited_unit' and medico_user.first_name == 'Synthetic'
    assert medico_user.last_name == 'Edited' and medico_user.email == 'edited@example.test'
    assert medico_user.rol == 'recepcionista' and not medico_user.is_active
    assert medico_user.check_password('medico123')


def test_patient_crud_keeps_ciphertext(auth_recepcionista):
    from pacientes.models import Paciente
    from django.db import connection
    data = {'nombres': 'Synthetic', 'apellidos': 'Crud', 'ci': 'CRUD-SYNTH-001', 'fecha_nacimiento': '1990-01-01', 'genero': 'F', 'telefono': '00000000'}
    created = auth_recepcionista.post('/api/pacientes/', data, format='json')
    assert created.status_code == 201
    pk = created.data['id']
    updated = auth_recepcionista.patch(f'/api/pacientes/{pk}/', {'ci': 'CRUD-SYNTH-002', 'telefono': '11111111'}, format='json')
    assert updated.status_code == 200
    with connection.cursor() as cursor:
        cursor.execute('SELECT ci FROM pacientes_paciente WHERE id=%s', [pk])
        assert cursor.fetchone()[0].startswith('neorx$1$')
    assert auth_recepcionista.get('/api/pacientes/?search=SYNTH-002').data['count'] == 1
    assert auth_recepcionista.delete(f'/api/pacientes/{pk}/').status_code == 204
    assert not Paciente.objects.filter(pk=pk).exists()


def test_recovery_email_code_and_email_login(api_client, medico_user, mailoutbox):
    import re
    original = api_client.post('/api/token/', {'username': medico_user.email.upper(), 'password': 'medico123'})
    assert original.status_code == 200
    assert AccessToken(original.data['access'])['username'] == medico_user.username
    assert api_client.post('/api/token/', {'username': medico_user.email, 'password': 'wrong'}).status_code == 401
    assert api_client.post('/api/password/reset/', {'email': 'missing@example.invalid'}).status_code == 404
    assert api_client.post('/api/password/reset/', {'email': medico_user.email.upper()}).status_code == 200
    assert len(mailoutbox) == 1
    body = mailoutbox[0].body
    code = re.search(r'código de recuperación es: (\d{6})', body).group(1)
    assert '#token=' not in body and code not in body.split('Si no solicitaste')[1]
    assert api_client.post('/api/password/reset/confirm/', {'email': medico_user.email, 'reset_proof': code, 'new_password': 'New-strong-password-552!'}).status_code == 400
    wrong = '000000' if code != '000000' else '000001'
    assert api_client.post('/api/password/reset/verify/', {'email': medico_user.email, 'code': wrong}).status_code == 400
    verified = api_client.post('/api/password/reset/verify/', {'email': medico_user.email.upper(), 'code': code})
    assert verified.status_code == 200
    proof = verified.data['reset_proof']
    assert len(proof) >= 32 and proof != code
    assert api_client.post('/api/password/reset/verify/', {'email': medico_user.email, 'code': code}).status_code == 400
    assert api_client.post('/api/password/reset/confirm/', {'email': medico_user.email, 'reset_proof': proof, 'new_password': '123'}).status_code == 400
    assert api_client.post('/api/password/reset/confirm/', {'email': medico_user.email, 'reset_proof': proof, 'new_password': 'New-strong-password-552!'}).status_code == 200
    assert api_client.post('/api/password/reset/confirm/', {'email': medico_user.email, 'reset_proof': proof, 'new_password': 'Another-password-553!'}).status_code == 400
    medico_user.refresh_from_db()
    assert medico_user.check_password('New-strong-password-552!') and medico_user.password_reset_token is None
    assert api_client.post('/api/token/refresh/', {'refresh': original.data['refresh']}).status_code == 401
    assert api_client.post('/api/token/', {'username': medico_user.email, 'password': 'New-strong-password-552!'}).status_code == 200
    assert api_client.get('/api/register/').status_code == 404


def test_recovery_wrong_codes_expiry_and_delivery_failure(api_client, medico_user, mailoutbox, monkeypatch):
    import re
    from accounts import views
    assert api_client.post('/api/password/reset/', {'email': medico_user.email}).status_code == 200
    code = re.search(r'código de recuperación es: (\d{6})', mailoutbox[-1].body).group(1)
    wrong = '000000' if code != '000000' else '000001'
    for _ in range(5):
        assert api_client.post('/api/password/reset/verify/', {'email': medico_user.email, 'code': wrong}).status_code == 400
    assert api_client.post('/api/password/reset/verify/', {'email': medico_user.email, 'code': code}).status_code == 400
    assert api_client.post('/api/password/reset/', {'email': medico_user.email}).status_code == 200
    code = re.search(r'código de recuperación es: (\d{6})', mailoutbox[-1].body).group(1)
    medico_user.refresh_from_db()
    medico_user.password_reset_expires = timezone.now() - timedelta(seconds=1)
    medico_user.save(update_fields=['password_reset_expires'])
    assert api_client.post('/api/password/reset/verify/', {'email': medico_user.email, 'code': code}).status_code == 400
    def fail(*args, **kwargs):
        raise OSError('mail transport unavailable')
    monkeypatch.setattr(views, 'send_mail', fail)
    assert api_client.post('/api/password/reset/', {'email': medico_user.email}).status_code == 503
    medico_user.refresh_from_db()
    assert medico_user.password_reset_token is None


def test_admin_cannot_assign_duplicate_recovery_email(auth_admin, medico_user):
    result = auth_admin.post('/api/admin/users/', {'username': 'duplicate_email_unit', 'email': medico_user.email.upper(), 'password': 'Strong-recovery-phrase-827!', 'rol': 'recepcionista'}, format='json')
    assert result.status_code == 400 and 'email' in result.data['errors']
