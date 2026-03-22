from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('team', '0002_contracthistory_remove_contract_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='collaborator',
            name='is_tns',
            field=models.BooleanField(default=False, verbose_name='Travailleur Non Salarié (TNS)'),
        ),
    ]
