from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0002_collaborator_civility_collaborator_color_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='collaborator',
            name='can_manage_account',
            field=models.BooleanField(default=False, verbose_name='Gérer le compte'),
        ),
        migrations.AddField(
            model_name='collaborator',
            name='can_manage_team',
            field=models.BooleanField(default=False, verbose_name="Gérer l'équipe"),
        ),
        migrations.AddField(
            model_name='collaborator',
            name='can_manage_planning',
            field=models.BooleanField(default=False, verbose_name='Gérer le planning'),
        ),
        migrations.AddField(
            model_name='collaborator',
            name='can_manage_quality',
            field=models.BooleanField(default=False, verbose_name='Gérer la qualité'),
        ),
    ]
