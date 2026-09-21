"""Cryptographic/storage regressions: synthetic identifiers, no keys in output."""
import io
from pathlib import Path
import pytest
from cryptography.fernet import Fernet
from django.db import connection, IntegrityError, transaction
from django.core.exceptions import ImproperlyConfigured
from django.db.migrations.executor import MigrationExecutor
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from pacientes.models import Paciente
from pacientes.serializers import PacienteSerializer
from estudios.models import ImagenDICOM
from neorx.encryption import DecryptionError, encrypt_text, decrypt_text, ci_digest
from neorx.models import AuditLog, log_audit

pytestmark = pytest.mark.django_db


def create_patient(ci='ENCRYPTION-SYNTH-01'):
    return Paciente.objects.create(nombres='Synthetic', apellidos='Encryption', ci=ci,
        fecha_nacimiento='1980-01-01', genero='M')


def raw_ci(pk):
    with connection.cursor() as cursor:
        cursor.execute('SELECT ci, ci_search_hash FROM pacientes_paciente WHERE id=%s',[pk])
        return cursor.fetchone()


def test_logical_roundtrip_and_physical_ciphertext():
    patient=create_patient()
    stored,digest=raw_ci(patient.pk)
    assert stored != patient.ci and patient.ci not in stored and stored.startswith('neorx$1$')
    assert len(digest)==64 and digest==ci_digest(patient.ci)
    assert Paciente.objects.get(pk=patient.pk).ci==patient.ci
    assert 'ci_search_hash' not in PacienteSerializer(patient).data


def test_ciphertext_randomized():
    assert encrypt_text('SYNTHETIC') != encrypt_text('SYNTHETIC')


def test_incorrect_key_never_silently_decrypts(settings):
    patient=create_patient()
    settings.FERNET_KEY=Fernet.generate_key().decode()
    with pytest.raises(DecryptionError):
        Paciente.objects.get(pk=patient.pk)


@pytest.mark.parametrize('stored',['PLAINTEXT-SENTINEL','neorx$1$invalid'])
def test_plaintext_and_corrupted_tokens_rejected(stored):
    patient=create_patient()
    with connection.cursor() as cursor:
        cursor.execute('UPDATE pacientes_paciente SET ci=%s WHERE id=%s',[stored,patient.pk])
    with pytest.raises(DecryptionError):
        Paciente.objects.get(pk=patient.pk)


def test_normalized_exact_search_and_uniqueness():
    patient=create_patient('12345678 LP')
    assert Paciente.objects.get(ci=' １２３４５６７８ lp ').pk==patient.pk
    assert Paciente.objects.get(ci__iexact='12345678lp').pk==patient.pk
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            create_patient('12345678lp')


def test_partial_search_remains_functional(auth_medico):
    patient=create_patient('SEARCH-728-LP')
    assert Paciente.objects.filter(ci__icontains='728').get().pk==patient.pk
    assert auth_medico.get('/api/pacientes/?ci=728').data['count']==1
    assert auth_medico.get('/api/pacientes/?search=728').data['count']==1
    assert auth_medico.get('/api/pacientes/buscar/?q=728').data[0]['id']==patient.pk


def test_model_edit_keeps_hmac_index():
    patient=create_patient('OLD-SYNTHETIC')
    patient.ci='NEW-SYNTHETIC';patient.save(update_fields=['ci'])
    assert Paciente.objects.filter(ci='NEW-SYNTHETIC').exists()
    assert not Paciente.objects.filter(ci='OLD-SYNTHETIC').exists()
    assert raw_ci(patient.pk)[1]==ci_digest('NEW-SYNTHETIC')
    with pytest.raises(ValueError):
        Paciente.objects.filter(pk=patient.pk).update(ci='UNSAFE')


def test_bulk_create_index_and_ciphertext():
    patients=Paciente.objects.bulk_create([Paciente(nombres='Unit',apellidos='Test',ci=f'BULK-{i}',fecha_nacimiento='1980-01-01',genero='M') for i in range(2)])
    assert all(raw_ci(p.pk)[0]!=p.ci for p in patients)
    assert Paciente.objects.filter(ci='BULK-1').exists()


@pytest.mark.parametrize('debug',[True,False])
def test_no_key_no_plaintext_fallback(settings,debug):
    settings.DEBUG=debug;settings.FERNET_KEY=None
    with pytest.raises(ImproperlyConfigured):
        create_patient()
    assert Paciente.objects.count()==0


def test_secrets_and_ci_not_logged(auth_medico, settings, caplog, capsys):
    sentinel='LOG-SYNTH-SECRET'
    patient=create_patient(sentinel)
    auth_medico.get('/api/pacientes/',{'ci':sentinel})
    log_audit(None,action='update',resource_type='unit',after={'ci':sentinel},metadata={'FERNET_KEY':settings.FERNET_KEY})
    entry=AuditLog.objects.get(resource_type='unit')
    assert entry.after['ci']=='[REDACTED]'
    assert settings.FERNET_KEY not in caplog.text and sentinel not in caplog.text
    assert settings.FERNET_KEY not in capsys.readouterr().out


def test_production_roundtrip(settings):
    settings.DEBUG=False
    patient=create_patient()
    assert Paciente.objects.get(pk=patient.pk).ci==patient.ci
    assert raw_ci(patient.pk)[0]!=patient.ci


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_rows_and_is_reversible():
    executor=MigrationExecutor(connection)
    leaves=executor.loader.graph.leaf_nodes()
    try:
        executor.migrate([('pacientes','0002_estudio_requiere_repeticion')])
        state=executor.loader.project_state([('pacientes','0002_estudio_requiere_repeticion')])
        patient_model=state.apps.get_model('pacientes','Paciente')
        study_model=state.apps.get_model('pacientes','Estudio')
        patient=patient_model.objects.create(nombres='Migration',apellidos='Unit',ci='MIGRATE-SYNTH-01',fecha_nacimiento='1980-01-01',genero='M')
        study=study_model.objects.create(paciente=patient,fecha='2026-01-01')
        executor=MigrationExecutor(connection);executor.migrate([('pacientes','0003_encrypt_ci')])
        assert Paciente.objects.get(pk=patient.pk).ci=='MIGRATE-SYNTH-01'
        assert raw_ci(patient.pk)[0]!='MIGRATE-SYNTH-01'
        from pacientes.models import Estudio
        assert Estudio.objects.get(pk=study.pk).paciente_id==patient.pk
        executor=MigrationExecutor(connection);executor.migrate([('pacientes','0002_estudio_requiere_repeticion')])
        with connection.cursor() as cursor:
            cursor.execute('SELECT ci FROM pacientes_paciente WHERE id=%s',[patient.pk])
            assert cursor.fetchone()[0]=='MIGRATE-SYNTH-01'
    finally:
        MigrationExecutor(connection).migrate(leaves)


def test_private_media_access_and_cache(auth_medico, imagen_dicom, settings, tmp_path):
    settings.MEDIA_ROOT=tmp_path
    imagen_dicom.archivo_png.save('private.png',SimpleUploadedFile('private.png',b'SYNTHETIC-PNG'))
    url=imagen_dicom.archivo_png.url
    assert APIClient().get(url).status_code==401
    response=auth_medico.get(url)
    assert response.status_code==200 and b''.join(response.streaming_content)==b'SYNTHETIC-PNG'
    assert 'no-store' in response['Cache-Control'] and response['X-Content-Type-Options']=='nosniff'
    assert auth_medico.get('/media/unregistered.png').status_code==404
    assert auth_medico.get('/media/../.env').status_code in [400,404]


def test_private_media_inactive_user(medico_user, imagen_dicom, settings, tmp_path):
    from rest_framework_simplejwt.tokens import RefreshToken
    settings.MEDIA_ROOT=tmp_path
    imagen_dicom.archivo_png.save('private.png',SimpleUploadedFile('private.png',b'SYNTHETIC-PNG'))
    token=str(RefreshToken.for_user(medico_user).access_token)
    client=APIClient();client.credentials(HTTP_AUTHORIZATION='Bearer '+token)
    medico_user.is_active=False;medico_user.save(update_fields=['is_active'])
    assert client.get(imagen_dicom.archivo_png.url).status_code==401


def test_nginx_media_cannot_bypass_authentication():
    root=Path(__file__).resolve().parents[2]
    for name in ['nginx/nginx.conf','nginx/conf.d/default.conf']:
        if not (root/name).exists():
            continue
        content=(root/name).read_text()
        section=content.split('location ^~ /media/')[1].split('}')[0]
        expected = 'proxy_pass http://backend;' if name == 'nginx/nginx.conf' else 'proxy_pass http://backend:8000;'
        assert expected in section and 'alias' not in section
        assert 'public' not in section


def test_ci_ordering_uses_logical_value(auth_medico):
    for ci in ['Z-SYNTH', 'A-SYNTH', 'M-SYNTH']:
        create_patient(ci)
    for order, expected in [('ci', ['A-SYNTH', 'M-SYNTH', 'Z-SYNTH']), ('-ci', ['Z-SYNTH', 'M-SYNTH', 'A-SYNTH'])]:
        response = auth_medico.get('/api/pacientes/', {'ordering': order})
        assert [p['ci'] for p in response.data['results']] == expected
