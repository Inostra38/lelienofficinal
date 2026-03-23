from django.db import migrations, models
import django.db.models.expressions


class Migration(migrations.Migration):

    dependencies = [
        ('planning', '0010_alter_absencerequest_collaborator'),
    ]

    operations = [
        # ── Index Shift ──────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='shift',
            index=models.Index(fields=['start_datetime'], name='shift_start_idx'),
        ),
        migrations.AddIndex(
            model_name='shift',
            index=models.Index(fields=['collaborator', 'start_datetime'], name='shift_collab_start_idx'),
        ),
        # ── Contrainte Shift ─────────────────────────────────────────────────────
        migrations.AddConstraint(
            model_name='shift',
            constraint=models.CheckConstraint(
                condition=models.Q(end_datetime__gt=django.db.models.expressions.F('start_datetime')),
                name='shift_end_after_start',
            ),
        ),
        # ── Index AbsenceRequest ─────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='absencerequest',
            index=models.Index(fields=['collaborator', 'status', 'start_date'], name='absence_collab_status_idx'),
        ),
        # ── Index TimeAdjustment ─────────────────────────────────────────────────
        migrations.AddIndex(
            model_name='timeadjustment',
            index=models.Index(fields=['collaborator', 'date'], name='timeadj_collab_date_idx'),
        ),
        # ── Contrainte TimeAdjustment ────────────────────────────────────────────
        migrations.AddConstraint(
            model_name='timeadjustment',
            constraint=models.CheckConstraint(
                condition=models.Q(duration_minutes__gt=0),
                name='timeadj_duration_positive',
            ),
        ),
    ]
