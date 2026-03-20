"""
Migration 0006 :
- Crée ProcedureCategory
- Remplace Procedure.category (CharField) par Procedure.categories (M2M)
  avec data migration des valeurs existantes
- Enrichit ProcedureAttachment (original_name, file_type, uploaded_by)
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


CATEGORY_LABELS = {
    'dispensation': 'Dispensation',
    'hygiene': 'Hygiène',
    'stock': 'Stock',
    'administratif': 'Administratif',
    'autre': 'Autre',
}


def migrate_categories_forward(apps, schema_editor):
    Procedure = apps.get_model('quality', 'Procedure')
    ProcedureCategory = apps.get_model('quality', 'ProcedureCategory')

    cache = {}  # (pharmacy_id, category_slug) → ProcedureCategory

    for proc in Procedure.objects.exclude(category='').filter(category__isnull=False):
        key = (proc.pharmacy_id, proc.category)
        if key not in cache:
            label = CATEGORY_LABELS.get(proc.category, proc.category.capitalize())
            cat, _ = ProcedureCategory.objects.get_or_create(
                name=label,
                pharmacy_id=proc.pharmacy_id,
                defaults={'color': '#2E7D32'},
            )
            cache[key] = cat
        proc.categories.add(cache[key])


def migrate_categories_backward(apps, schema_editor):
    """
    Restaure le champ category depuis la première catégorie M2M de chaque procédure.
    Mapping inverse approximatif.
    """
    Procedure = apps.get_model('quality', 'Procedure')

    REVERSE_LABELS = {v: k for k, v in CATEGORY_LABELS.items()}

    for proc in Procedure.objects.all():
        first_cat = proc.categories.first()
        if first_cat:
            proc.category = REVERSE_LABELS.get(first_cat.name, 'autre')
        else:
            proc.category = 'autre'
        proc.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('quality', '0005_procedureversion'),
        ('team', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Crée ProcedureCategory
        migrations.CreateModel(
            name='ProcedureCategory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('color', models.CharField(default='#2E7D32', max_length=7)),
                ('pharmacy', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='procedure_categories',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('created_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='created_procedure_categories',
                    to='team.collaborator',
                )),
            ],
            options={
                'verbose_name': 'Catégorie de procédure',
                'verbose_name_plural': 'Catégories de procédure',
                'ordering': ['name'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='procedurecategory',
            unique_together={('name', 'pharmacy')},
        ),

        # 2. Ajoute M2M categories sur Procedure
        migrations.AddField(
            model_name='procedure',
            name='categories',
            field=models.ManyToManyField(
                blank=True,
                related_name='procedures',
                to='quality.procedurecategory',
            ),
        ),

        # 3. Data migration : ancien category → nouvelles ProcedureCategory liées
        migrations.RunPython(
            migrate_categories_forward,
            migrate_categories_backward,
        ),

        # 4. Supprime l'ancien champ category
        migrations.RemoveField(
            model_name='procedure',
            name='category',
        ),

        # 5. Enrichit ProcedureAttachment
        migrations.AddField(
            model_name='procedureattachment',
            name='original_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='procedureattachment',
            name='file_type',
            field=models.CharField(
                choices=[('image', 'Image'), ('document', 'Document')],
                default='document',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='procedureattachment',
            name='uploaded_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='uploaded_attachments',
                to='team.collaborator',
            ),
        ),

        # 6. Met à jour upload_to pour les nouveaux attachments
        migrations.AlterField(
            model_name='procedureattachment',
            name='file',
            field=models.FileField(upload_to='quality/attachments/%Y/%m/'),
        ),
    ]
