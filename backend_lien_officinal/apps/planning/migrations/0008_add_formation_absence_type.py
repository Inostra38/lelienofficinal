from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0007_add_justifiee_absence_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='absencerequest',
            name='type',
            field=models.CharField(
                choices=[
                    ('injustifiee', 'Absence injustifiée'),
                    ('cp', 'Congés payés'),
                    ('maladie', 'Maladie'),
                    ('rcr', 'RCR'),
                    ('sans_solde', 'Sans solde'),
                    ('formation', 'Formation'),
                ],
                default='injustifiee',
                max_length=20,
            ),
        ),
    ]
