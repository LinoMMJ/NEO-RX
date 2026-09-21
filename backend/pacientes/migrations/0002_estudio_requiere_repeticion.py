from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pacientes", "0001_initial")]
    operations = [migrations.AlterField(
        model_name="estudio", name="estado",
        field=models.CharField(max_length=20, default="pendiente", choices=[
            ("pendiente", "Pendiente"), ("en_proceso", "En Proceso"),
            ("completado", "Completado"), ("requiere_repeticion", "Requiere repetición")]))]
