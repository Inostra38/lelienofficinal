from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0006_populate_wizard_categories'),
    ]

    operations = [
        migrations.AddField(
            model_name='wizardcategory',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
    ]
