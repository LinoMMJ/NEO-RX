"""Remove unnecessary copies of identifiers from historical audit payloads."""
from django.db import migrations


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).lower() in {"ci", "filename"} else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def forward(apps, schema_editor):
    audit = apps.get_model("neorx", "AuditLog")
    for entry in audit.objects.using(schema_editor.connection.alias).iterator():
        fields = {name: redact(getattr(entry, name)) for name in ("before", "after", "metadata")}
        audit.objects.using(schema_editor.connection.alias).filter(pk=entry.pk).update(**fields)


class Migration(migrations.Migration):
    dependencies = [("neorx", "0002_alter_auditlog_action")]
    operations = [migrations.RunPython(forward, migrations.RunPython.noop)]
