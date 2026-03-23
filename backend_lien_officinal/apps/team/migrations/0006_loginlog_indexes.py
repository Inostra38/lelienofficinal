from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0005_collaboratorloginlog'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='collaboratorloginlog',
            index=models.Index(fields=['pharmacy', '-timestamp'], name='loginlog_pharmacy_ts_idx'),
        ),
        migrations.AddIndex(
            model_name='collaboratorloginlog',
            index=models.Index(
                fields=['pharmacy'],
                condition=models.Q(success=False),
                name='loginlog_failures_idx',
            ),
        ),
    ]
