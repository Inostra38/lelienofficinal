from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0013_absencerequest_half_day'),
    ]

    operations = [
        # Supprimer l'ancienne contrainte
        migrations.RemoveConstraint(
            model_name='absencerequest',
            name='absence_half_day_requires_single_day',
        ),
        # Supprimer les anciens champs
        migrations.RemoveField(model_name='absencerequest', name='half_day'),
        migrations.RemoveField(model_name='absencerequest', name='half_day_period'),
        # Ajouter les nouveaux champs
        migrations.AddField(
            model_name='absencerequest',
            name='start_period',
            field=models.CharField(
                choices=[('morning', 'Matin'), ('afternoon', 'Après-midi')],
                default='morning',
                max_length=9,
            ),
        ),
        migrations.AddField(
            model_name='absencerequest',
            name='end_period',
            field=models.CharField(
                choices=[('morning', 'Matin'), ('evening', 'Soir')],
                default='evening',
                max_length=7,
            ),
        ),
    ]
