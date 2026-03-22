from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0008_add_formation_absence_type'),
    ]

    operations = [
        # Renomme la valeur 'justifiee' → 'conge_exceptionnel' dans les données existantes
        migrations.RunSQL(
            sql="UPDATE planning_shift SET absence_type = 'conge_exceptionnel' WHERE absence_type = 'justifiee'",
            reverse_sql="UPDATE planning_shift SET absence_type = 'justifiee' WHERE absence_type = 'conge_exceptionnel'",
        ),
        migrations.RunSQL(
            sql="UPDATE planning_absencerequest SET type = 'conge_exceptionnel' WHERE type = 'justifiee'",
            reverse_sql="UPDATE planning_absencerequest SET type = 'justifiee' WHERE type = 'conge_exceptionnel'",
        ),
        # Met à jour les choices sur le champ Shift.absence_type
        migrations.AlterField(
            model_name='shift',
            name='absence_type',
            field=models.CharField(
                blank=True,
                choices=[
                    ('injustifiee',        'Absence injustifiée'),
                    ('conge_exceptionnel', 'Congé exceptionnel légal'),
                    ('maladie',            'Maladie'),
                    ('cp',                 'Congés payés'),
                    ('rcr',                'RCR'),
                    ('sans_solde',         'Sans solde'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        # Met à jour les choices sur le champ AbsenceRequest.type
        migrations.AlterField(
            model_name='absencerequest',
            name='type',
            field=models.CharField(
                choices=[
                    ('injustifiee',        'Absence injustifiée'),
                    ('conge_exceptionnel', 'Congé exceptionnel légal'),
                    ('cp',                 'Congés payés'),
                    ('maladie',            'Maladie'),
                    ('rcr',                'RCR'),
                    ('sans_solde',         'Sans solde'),
                    ('formation',          'Formation'),
                ],
                default='injustifiee',
                max_length=20,
            ),
        ),
    ]
