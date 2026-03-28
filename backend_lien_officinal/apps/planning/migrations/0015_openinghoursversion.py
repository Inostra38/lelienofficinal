from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0014_absencerequest_periods'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='OpeningHoursVersion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('effective_from', models.DateField(
                    help_text="Lundi de la semaine à partir de laquelle ces horaires s'appliquent"
                )),
                ('pharmacy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='opening_hours_versions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['effective_from'],
                'unique_together': {('pharmacy', 'effective_from')},
            },
        ),
        migrations.AddField(
            model_name='openinghours',
            name='version',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='slots',
                to='planning.openinghoursversion',
            ),
        ),
    ]
