import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _


class Task(models.Model):

    class Priority(models.TextChoices):
        HIGH = 'HIGH', _('Haute')
        MEDIUM = 'MEDIUM', _('Moyenne')
        LOW = 'LOW', _('Basse')

    class Status(models.TextChoices):
        TODO = 'TODO', _('À faire')
        IN_PROGRESS = 'IN_PROGRESS', _('En cours')
        DONE = 'DONE', _('Terminée')

    class TaskType(models.TextChoices):
        PERSONAL = 'PERSONAL', _('Tâche propre')
        ASSIGNED = 'ASSIGNED', _('Tâche assignée')

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_("Pharmacie")
    )

    title = models.CharField(_("Titre"), max_length=200)
    description = models.TextField(_("Description"), blank=True)
    priority = models.CharField(
        _("Priorité"), max_length=10,
        choices=Priority.choices, default=Priority.MEDIUM
    )
    status = models.CharField(
        _("Statut"), max_length=15,
        choices=Status.choices, default=Status.TODO
    )
    type = models.CharField(
        _("Type"), max_length=10,
        choices=TaskType.choices, default=TaskType.PERSONAL
    )

    created_by = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_tasks',
        verbose_name=_("Créé par")
    )
    assigned_to = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_tasks',
        verbose_name=_("Assigné à")
    )

    due_date = models.DateField(_("Date d'échéance"), null=True, blank=True)
    started_at = models.DateTimeField(_("Démarrée le"), null=True, blank=True)
    completed_at = models.DateTimeField(_("Terminée le"), null=True, blank=True)
    is_completion_seen = models.BooleanField(_("Completion vue"), default=False)
    order = models.PositiveIntegerField(_("Ordre"), default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Tâche")
        verbose_name_plural = _("Tâches")
        ordering = ['order', '-created_at']

    def __str__(self):
        return f"{self.title}"


class TaskComment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        related_name='task_comments'
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.task}] {self.author}: {self.content[:40]}"
