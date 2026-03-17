from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_remove_customvariable'),
    ]

    operations = [
        migrations.AddField(
            model_name='smslog',
            name='motif',
            field=models.CharField(blank=True, default='', max_length=255),
        ),
    ]
