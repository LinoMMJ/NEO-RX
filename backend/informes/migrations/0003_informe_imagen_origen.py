from django.db import migrations, models
import django.db.models.deletion


def associate_existing(apps, schema_editor):
    Report = apps.get_model('informes', 'InformePreliminar')
    Image = apps.get_model('estudios', 'ImagenDICOM')
    alias = schema_editor.connection.alias
    for report in Report.objects.using(alias).filter(imagen_origen__isnull=True).iterator():
        image = Image.objects.using(alias).filter(estudio_id=report.estudio_id).order_by('-fecha_subida').first()
        if image:
            Report.objects.using(alias).filter(pk=report.pk).update(imagen_origen_id=image.pk)


class Migration(migrations.Migration):
    dependencies = [('informes', '0002_informepreliminar_correlacion_clinica'),
                    ('estudios', '0004_backfill_legacy_cnn_eligibility')]
    operations = [
        migrations.AddField(
            model_name='informepreliminar', name='imagen_origen',
            field=models.ForeignKey(null=True, blank=True, on_delete=django.db.models.deletion.RESTRICT,
                                    related_name='informes_origen', to='estudios.imagendicom'),
        ),
        migrations.RunPython(associate_existing, migrations.RunPython.noop),
    ]
