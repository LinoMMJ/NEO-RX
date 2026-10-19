from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("informes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="informepreliminar",
            name="correlacion_clinica",
            field=models.TextField(blank=True),
        ),
    ]
