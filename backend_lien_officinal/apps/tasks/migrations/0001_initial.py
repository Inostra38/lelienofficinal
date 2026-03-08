import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('team', '0002_collaborator_civility_collaborator_color_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('title', models.CharField(max_length=200, verbose_name='Titre')),
                ('description', models.TextField(blank=True, verbose_name='Description')),
                ('priority', models.CharField(
                    choices=[('HIGH', 'Haute'), ('MEDIUM', 'Moyenne'), ('LOW', 'Basse')],
                    default='MEDIUM', max_length=10, verbose_name='Priorité'
                )),
                ('status', models.CharField(
                    choices=[('TODO', 'À faire'), ('IN_PROGRESS', 'En cours'), ('DONE', 'Terminée')],
                    default='TODO', max_length=15, verbose_name='Statut'
                )),
                ('type', models.CharField(
                    choices=[('PERSONAL', 'Tâche propre'), ('ASSIGNED', 'Tâche assignée')],
                    default='PERSONAL', max_length=10, verbose_name='Type'
                )),
                ('due_date', models.DateField(blank=True, null=True, verbose_name="Date d'échéance")),
                ('completed_at', models.DateTimeField(blank=True, null=True, verbose_name='Terminée le')),
                ('is_completion_seen', models.BooleanField(default=False, verbose_name='Completion vue')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pharmacy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='tasks',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Pharmacie'
                )),
                ('assigned_to', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='assigned_tasks',
                    to='team.collaborator',
                    verbose_name='Assigné à'
                )),
                ('created_by', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_tasks',
                    to='team.collaborator',
                    verbose_name='Créé par'
                )),
            ],
            options={
                'verbose_name': 'Tâche',
                'verbose_name_plural': 'Tâches',
                'ordering': ['-created_at'],
            },
        ),
    ]
