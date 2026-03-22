from django.conf import settings
from django.db import models


class PharmacyDayStatus(models.Model):
    class Status(models.TextChoices):
        OPEN   = 'open',   'Ouvert'
        CLOSED = 'closed', 'Fermé'

    pharmacy      = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='day_statuses',
    )
    date          = models.DateField()
    status        = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    on_call_day   = models.BooleanField(default=False)
    on_call_night = models.BooleanField(default=False)
    note          = models.TextField(blank=True)

    class Meta:
        unique_together = ('pharmacy', 'date')
        ordering = ['date']

    def __str__(self):
        return f"{self.pharmacy} — {self.date} — {self.status}"


class PlanningSettings(models.Model):
    class DraftWindow(models.IntegerChoices):
        TWO   = 2, '2 semaines'
        THREE = 3, '3 semaines'
        FOUR  = 4, '4 semaines'

    pharmacy = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='planning_settings',
    )
    draft_window = models.IntegerField(choices=DraftWindow.choices, default=DraftWindow.TWO)

    # Créneaux de garde
    on_call_day_start   = models.TimeField(null=True, blank=True)
    on_call_day_end     = models.TimeField(null=True, blank=True)
    on_call_night_start = models.TimeField(null=True, blank=True)
    on_call_night_end   = models.TimeField(null=True, blank=True)

    # Dimanche toujours en garde de jour (sauf entrée explicite)
    on_call_sunday = models.BooleanField(default=False)

    def __str__(self):
        return f"Paramètres planning — {self.pharmacy}"


class OpeningHours(models.Model):
    """Créneau d'ouverture hebdomadaire de la pharmacie (plusieurs possibles par jour)."""
    DAY_CHOICES = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
        (4, 'Vendredi'), (5, 'Samedi'),
        # Dimanche (6) toujours fermé — non configurable
    ]

    pharmacy    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='opening_hours',
    )
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time  = models.TimeField()
    end_time    = models.TimeField()

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.pharmacy} — Jour {self.day_of_week} {self.start_time}–{self.end_time}"


class Shift(models.Model):
    collaborator   = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='shifts',
    )
    collaborator_snapshot = models.CharField(
        max_length=150, blank=True,
        help_text="Nom capturé à la publication, préservé si le collab est archivé"
    )
    start_datetime = models.DateTimeField()
    end_datetime   = models.DateTimeField()
    is_published   = models.BooleanField(default=False)
    is_extra_hour  = models.BooleanField(default=False)
    is_absent      = models.BooleanField(default=False)
    absence_type   = models.CharField(
        max_length=20,
        choices=[
            ('injustifiee', 'Absence injustifiée'),
            ('maladie',     'Maladie'),
            ('cp',          'Congés payés'),
            ('rcr',         'RCR'),
            ('sans_solde',  'Sans solde'),
        ],
        null=True, blank=True,
    )
    note           = models.TextField(blank=True)
    # Snapshot des heures contractuelles au moment de la création du shift
    # Permet de préserver l'exactitude des stats historiques si le contrat évolue
    contract_hours_snapshot = models.DecimalField(
        max_digits=4, decimal_places=1, null=True, blank=True,
        help_text="Heures hebdo contractuelles du collaborateur à la date de création du shift"
    )
    created_at     = models.DateTimeField(auto_now_add=True)
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['start_datetime']

    def __str__(self):
        name = self.collaborator_snapshot or str(self.collaborator) or "—"
        return f"{name} — {self.start_datetime:%Y-%m-%d %H:%M}"

    def save(self, *args, **kwargs):
        # Capture les heures contractuelles à la création uniquement
        if self._state.adding and self.collaborator and self.contract_hours_snapshot is None:
            self.contract_hours_snapshot = self.collaborator.weekly_hours
        super().save(*args, **kwargs)


class AbsenceRequest(models.Model):
    class AbsenceType(models.TextChoices):
        INJUSTIFIEE = 'injustifiee', 'Absence injustifiée'
        CP          = 'cp',          'Congés payés'
        MALADIE     = 'maladie',     'Maladie'
        RCR         = 'rcr',         'RCR'
        SANS_SOLDE  = 'sans_solde',  'Sans solde'

    class Status(models.TextChoices):
        PENDING  = 'pending',  'En attente'
        APPROVED = 'approved', 'Approuvée'
        REJECTED = 'rejected', 'Refusée'

    collaborator = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.CASCADE,
        related_name='absence_requests',
    )
    start_date  = models.DateField()
    end_date    = models.DateField()
    type        = models.CharField(max_length=20, choices=AbsenceType.choices, default=AbsenceType.INJUSTIFIEE)
    status      = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    note        = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reviewed_absences',
    )
    posted_by_manager = models.BooleanField(
        default=False,
        help_text="True si posé directement par un manager sans demande du collaborateur",
    )

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.collaborator} — {self.type} — {self.status}"


# ── Templates semaine ──────────────────────────────────────────────────────────

class WeekTemplate(models.Model):
    """Planning type répétable (semaine A, B, C ou D)."""
    class Letter(models.TextChoices):
        A = 'A', 'Semaine A'
        B = 'B', 'Semaine B'
        C = 'C', 'Semaine C'
        D = 'D', 'Semaine D'

    pharmacy   = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='week_templates',
    )
    letter     = models.CharField(max_length=1, choices=Letter.choices)
    apply_from = models.DateField(
        null=True, blank=True,
        help_text="Date à partir de laquelle ce template est appliqué",
    )

    class Meta:
        unique_together = ('pharmacy', 'letter')

    def __str__(self):
        return f"Template {self.letter} — {self.pharmacy}"


class TemplateShift(models.Model):
    """Shift générique dans un template (sans date réelle)."""
    DAY_CHOICES = [
        (0, 'Lundi'), (1, 'Mardi'), (2, 'Mercredi'), (3, 'Jeudi'),
        (4, 'Vendredi'), (5, 'Samedi'), (6, 'Dimanche'),
    ]

    template     = models.ForeignKey(WeekTemplate, on_delete=models.CASCADE, related_name='shifts')
    collaborator = models.ForeignKey('team.Collaborator', on_delete=models.CASCADE)
    day_of_week  = models.IntegerField(choices=DAY_CHOICES)
    start_time   = models.TimeField()
    end_time     = models.TimeField()
    note         = models.TextField(blank=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"Template {self.template.letter} — Jour {self.day_of_week} — {self.collaborator}"


class WeekTemplateApplication(models.Model):
    """Trace quelle lettre de template a été appliquée à quelle semaine."""
    pharmacy   = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    week_start = models.DateField()
    letter     = models.CharField(max_length=1)
    applied_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pharmacy', 'week_start')

    def __str__(self):
        return f"Semaine {self.week_start} → Template {self.letter}"


class TimeAdjustment(models.Model):
    class Type(models.TextChoices):
        OVERTIME        = 'overtime',        'Heures supplémentaires'
        EARLY_DEPARTURE = 'early_departure', 'Départ anticipé'

    collaborator     = models.ForeignKey('team.Collaborator', on_delete=models.CASCADE, related_name='time_adjustments')
    date             = models.DateField()
    type             = models.CharField(max_length=20, choices=Type.choices)
    actual_time      = models.TimeField()          # heure réelle de fin/départ
    reference_time   = models.TimeField()          # heure planifiée de fin de shift
    duration_minutes = models.IntegerField()       # delta en minutes (toujours positif, sens donné par type)
    shift            = models.ForeignKey('Shift', null=True, blank=True, on_delete=models.SET_NULL, related_name='adjustments')
    note             = models.CharField(max_length=255, blank=True)
    declared_by      = models.ForeignKey('team.Collaborator', null=True, blank=True, on_delete=models.SET_NULL, related_name='declared_adjustments')
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-created_at']


# ── Contraintes planning ────────────────────────────────────────────────────────

class ConstraintSet(models.Model):
    pharmacy   = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='constraint_set'
    )
    updated_at = models.DateTimeField(auto_now=True)


class Constraint(models.Model):
    class Level(models.TextChoices):
        REGULATORY = 'regulatory', 'Réglementaire'
        PHARMACY   = 'pharmacy',   'Pharmacie'
        PERSONAL   = 'personal',   'Personnelle'

    constraint_set = models.ForeignKey(
        ConstraintSet, on_delete=models.CASCADE, related_name='constraints'
    )
    level       = models.CharField(max_length=20, choices=Level.choices)
    collaborator = models.ForeignKey(
        'team.Collaborator', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='personal_constraints'
    )
    description = models.TextField()
    is_active   = models.BooleanField(default=True)
    order       = models.IntegerField(default=0)

    class Meta:
        ordering = ['level', 'order']
