from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0007_add_archived_at_to_collaborator'),
    ]

    operations = [
        migrations.AddField(
            model_name='collaborator',
            name='can_manage_procedures',
            field=models.BooleanField(default=False, verbose_name='Gérer les procédures'),
        ),
        migrations.AddField(
            model_name='collaborator',
            name='can_publish_procedures',
            field=models.BooleanField(default=False, verbose_name='Publier les procédures'),
        ),
        migrations.AddField(
            model_name='collaborator',
            name='can_close_nonconformities',
            field=models.BooleanField(default=False, verbose_name='Clôturer les non-conformités'),
        ),
    ]
