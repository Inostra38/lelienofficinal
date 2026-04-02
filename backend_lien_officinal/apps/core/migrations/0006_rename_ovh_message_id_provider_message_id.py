from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_email_verified'),
    ]

    operations = [
        migrations.RenameField(
            model_name='smslog',
            old_name='ovh_message_id',
            new_name='provider_message_id',
        ),
    ]
