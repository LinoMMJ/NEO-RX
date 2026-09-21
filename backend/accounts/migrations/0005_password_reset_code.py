from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [('accounts', '0004_customuser_password_reset_expires_and_more')]
    operations = [
        migrations.AddField(model_name='customuser', name='password_reset_attempts', field=models.PositiveSmallIntegerField(default=0)),
        migrations.AddField(model_name='customuser', name='password_reset_verified', field=models.BooleanField(default=False)),
    ]
