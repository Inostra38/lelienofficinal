import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_pharmacy_onboarding_completed'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='pending_email',
            field=models.EmailField(blank=True, null=True, verbose_name='Email en attente'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='email_verification_token',
            field=models.UUIDField(blank=True, null=True, verbose_name='Token de vérification email'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='email_verification_expires',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Expiration du token'),
        ),
    ]
