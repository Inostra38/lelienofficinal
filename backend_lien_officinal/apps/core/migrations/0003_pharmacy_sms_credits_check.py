from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_smslog_pending_delivered_ovh_id'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='pharmacy',
            constraint=models.CheckConstraint(
                condition=models.Q(sms_credits__gte=0),
                name='pharmacy_sms_credits_non_negative',
            ),
        ),
    ]
