import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quality', '0002_remove_procedure_file'),
        ('team', '0005_collaboratorloginlog'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProcedureReadLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('version_number', models.PositiveIntegerField()),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('collaborator', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='procedure_read_logs',
                    to='team.collaborator',
                )),
                ('procedure', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='read_logs',
                    to='quality.procedure',
                )),
            ],
            options={
                'verbose_name': 'Lecture de procédure',
                'verbose_name_plural': 'Lectures de procédures',
                'ordering': ['-read_at'],
            },
        ),
    ]
