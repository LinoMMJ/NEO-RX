from django.db import migrations


def mark_legacy_cnn_images(apps, schema_editor):
    Image = apps.get_model("estudios", "ImagenDICOM")
    Image.objects.filter(resultado_cnn__isnull=False).update(
        clasificacion_imagen="chest_xray",
        region_anatomica="Torax",
        es_radiografia=True,
        apta_para_cnn=True,
        fuente_clasificacion="legacy_cnn_result",
        motivo_no_cnn="",
    )


def reverse_mark(apps, schema_editor):
    Image = apps.get_model("estudios", "ImagenDICOM")
    Image.objects.filter(fuente_clasificacion="legacy_cnn_result").update(
        clasificacion_imagen="indeterminate",
        region_anatomica="",
        es_radiografia=None,
        apta_para_cnn=False,
        fuente_clasificacion="",
    )


class Migration(migrations.Migration):
    dependencies = [
        ("diagnostico", "0001_initial"),
        ("estudios", "0003_imagendicom_apta_para_cnn_and_more"),
    ]

    operations = [
        migrations.RunPython(mark_legacy_cnn_images, reverse_mark),
    ]
