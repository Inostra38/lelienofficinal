from django.db import migrations


def flatten_procedures(apps, schema_editor):
    """
    Met tous les parent_id à NULL pour aplatir l'arborescence des procédures.
    Les procédures gardent leur group et position ; seule la hiérarchie disparaît.
    """
    Procedure = apps.get_model('quality', 'Procedure')
    nested = Procedure.objects.filter(parent__isnull=False)
    count = nested.count()
    nested.update(parent=None)
    print(f"\n[E8] Flattened {count} nested procedure(s) → parent_id = NULL")


class Migration(migrations.Migration):

    dependencies = [
        ('quality', '0007_proceduregroup_order_procedure_archive_fields'),
    ]

    operations = [
        migrations.RunPython(flatten_procedures, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='procedure',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='procedure',
            name='is_group',
        ),
    ]
