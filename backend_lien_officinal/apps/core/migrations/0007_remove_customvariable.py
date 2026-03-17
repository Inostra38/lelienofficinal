from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_pharmacy_phone_customvariable'),
    ]

    operations = [
        migrations.DeleteModel(
            name='CustomVariable',
        ),
    ]
