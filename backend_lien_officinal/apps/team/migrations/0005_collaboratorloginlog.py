import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0004_alter_contracthistory_collaborator'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CollaboratorLoginLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='Adresse IP')),
                ('success', models.BooleanField(default=False, verbose_name='Succès')),
                ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Date/heure')),
                ('failure_reason', models.CharField(blank=True, default='', max_length=100, verbose_name="Raison de l'échec")),
                ('collaborator', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='login_logs',
                    to='team.collaborator',
                    verbose_name='Collaborateur',
                )),
                ('pharmacy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='collaborator_login_logs',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Pharmacie',
                )),
            ],
            options={
                'verbose_name': 'Journal connexion collaborateur',
                'verbose_name_plural': 'Journaux connexions collaborateurs',
                'ordering': ['-timestamp'],
            },
        ),
    ]
