"""Atomic, reversible plaintext CI -> authenticated ciphertext/index conversion."""
from django.db import migrations, models
import neorx.fields
from neorx.encryption import encrypt_text, decrypt_text, ci_digest


def convert(apps, schema_editor, reverse=False):
    patient = apps.get_model("pacientes", "Paciente")
    quote = schema_editor.connection.ops.quote_name
    table = quote(patient._meta.db_table)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"SELECT id, ci FROM {table}")
        rows = cursor.fetchall()
        prepared = []
        seen = set()
        for pk, stored in rows:
            logical = decrypt_text(stored) if reverse else stored
            if not isinstance(logical, str) or len(logical) > 20:
                raise RuntimeError("CI previo requiere revisión de formato; migración cancelada sin exponer datos.")
            digest = ci_digest(logical)
            if digest in seen:
                raise RuntimeError("CI duplicado tras normalización; migración cancelada sin modificar datos.")
            seen.add(digest)
            prepared.append((logical if reverse else encrypt_text(logical), digest, pk))
        cursor.executemany(f"UPDATE {table} SET ci = %s, ci_search_hash = %s WHERE id = %s", prepared)


def forward(apps, schema_editor):
    convert(apps, schema_editor)


def backward(apps, schema_editor):
    convert(apps, schema_editor, reverse=True)


class Migration(migrations.Migration):
    dependencies = [("pacientes", "0002_estudio_requiere_repeticion")]
    operations = [
        migrations.AddField(model_name="paciente", name="ci_search_hash",
            field=models.CharField(max_length=64, null=True, unique=True, editable=False)),
        migrations.AlterField(model_name="paciente", name="ci",
            field=neorx.fields.EncryptedCIField(max_length=20)),
        migrations.RunPython(forward, backward),
        migrations.AlterField(model_name="paciente", name="ci_search_hash",
            field=models.CharField(max_length=64, unique=True, editable=False)),
    ]
