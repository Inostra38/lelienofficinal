from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quality', '0003_procedurereadlog'),
    ]

    operations = [
        # ── Suppression unique_together (remplacé par UniqueConstraint conditionnel) ──
        migrations.AlterUniqueTogether(
            name='procedure',
            unique_together=set(),
        ),
        # ── Index composé pharmacy+status ─────────────────────────────────────────
        migrations.AddIndex(
            model_name='procedure',
            index=models.Index(fields=['pharmacy', 'status'], name='proc_pharmacy_status_idx'),
        ),
        # ── Index partiel : procédures actives seulement ─────────────────────────
        migrations.AddIndex(
            model_name='procedure',
            index=models.Index(
                fields=['pharmacy'],
                condition=models.Q(status='active'),
                name='proc_active_idx',
            ),
        ),
        # ── UniqueConstraint NULL-safe (reference non-nul uniquement) ────────────
        migrations.AddConstraint(
            model_name='procedure',
            constraint=models.UniqueConstraint(
                fields=['pharmacy', 'reference'],
                condition=models.Q(reference__isnull=False),
                name='proc_unique_pharmacy_reference',
            ),
        ),
    ]
