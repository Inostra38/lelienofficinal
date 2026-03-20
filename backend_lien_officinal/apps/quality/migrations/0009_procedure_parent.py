from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('quality', '0008_remove_parent_and_is_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='procedure',
            name='parent',
            field=models.ForeignKey(
                'self',
                null=True, blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='children',
            ),
        ),
    ]
