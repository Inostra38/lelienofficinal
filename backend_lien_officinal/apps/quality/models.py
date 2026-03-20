from django.db import models
from django.core.exceptions import ValidationError
from django.conf import settings


class ProcedureGroup(models.Model):
    """Tableau de procédures — espace de travail indépendant de la bibliothèque."""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#2E7D32')
    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='procedure_groups',
    )
    created_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_procedure_groups',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        unique_together = [['name', 'pharmacy']]
        verbose_name = 'Tableau de procédures'
        verbose_name_plural = 'Tableaux de procédures'

    def __str__(self):
        return self.name


class ProcedureCategory(models.Model):
    """Étiquette libre de catégorisation des procédures, par pharmacie."""
    name = models.CharField(max_length=100)
    color = models.CharField(max_length=7, default='#2E7D32')
    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='procedure_categories',
    )
    created_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_procedure_categories',
    )

    class Meta:
        unique_together = ('name', 'pharmacy')
        ordering = ['name']
        verbose_name = 'Catégorie de procédure'
        verbose_name_plural = 'Catégories de procédure'

    def __str__(self):
        return self.name


class Procedure(models.Model):

    class Status(models.TextChoices):
        DRAFT    = 'draft',    'Brouillon'
        ACTIVE   = 'active',   'Active'
        ARCHIVED = 'archived', 'Archivée'

    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='procedures',
    )
    title = models.CharField(max_length=200)
    reference = models.CharField(max_length=20, null=True, blank=True, default=None)
    is_group = models.BooleanField(default=False)
    categories = models.ManyToManyField(
        'ProcedureCategory',
        blank=True,
        related_name='procedures',
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    content = models.TextField(blank=True)
    file = models.FileField(upload_to='quality/procedures/', null=True, blank=True)
    version = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey(
        'self',
        null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='children',
    )
    position = models.PositiveIntegerField(default=0)
    group = models.ForeignKey(
        'ProcedureGroup',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='procedures',
    )
    pilots = models.ManyToManyField(
        'team.Collaborator',
        blank=True,
        related_name='piloted_procedures',
    )
    created_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='created_procedures',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('pharmacy', 'reference')
        verbose_name = 'Procédure'
        verbose_name_plural = 'Procédures'
        ordering = ['position', 'id']

    def __str__(self):
        ref = f"[{self.reference}] " if self.reference else ""
        return f"{ref}{self.title}"

    def get_depth(self):
        depth = 0
        node = self
        while node.parent_id is not None:
            depth += 1
            node = node.parent
        return depth

    def clean(self):
        if self.get_depth() > 2:
            raise ValidationError(
                "La profondeur maximale de l'arborescence est de 3 niveaux (0, 1, 2)."
            )


class ProcedureAttachment(models.Model):
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to='quality/attachments/%Y/%m/')
    filename = models.CharField(max_length=255)
    original_name = models.CharField(max_length=255, blank=True)
    file_type = models.CharField(
        max_length=20,
        choices=[('image', 'Image'), ('document', 'Document')],
        default='document',
    )
    uploaded_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='uploaded_attachments',
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Pièce jointe'
        verbose_name_plural = 'Pièces jointes'

    def __str__(self):
        return self.filename


class ProcedureImage(models.Model):
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name='images',
    )
    image = models.ImageField(upload_to='quality/images/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Image'
        verbose_name_plural = 'Images'


class ProcedureVersion(models.Model):
    """Historique des versions d'une procédure (Audit Trail)."""
    procedure = models.ForeignKey(
        Procedure,
        on_delete=models.CASCADE,
        related_name='history',
        verbose_name='Procédure'
    )
    version_number = models.PositiveIntegerField('Numéro de version')
    content = models.TextField('Contenu')
    change_summary = models.CharField('Résumé des modifications', max_length=255, blank=True)
    created_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='authored_versions',
        verbose_name='Auteur'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-version_number']
        unique_together = ('procedure', 'version_number')
        verbose_name = 'Version de procédure'
        verbose_name_plural = 'Versions de procédure'

    def __str__(self):
        return f"{self.procedure.title} - v{self.version_number}"


class NonConformity(models.Model):

    class Severity(models.TextChoices):
        MINOR    = 'minor',    'Mineure'
        MAJOR    = 'major',    'Majeure'
        CRITICAL = 'critical', 'Critique'

    class Status(models.TextChoices):
        OPEN        = 'open',        'Ouverte'
        IN_PROGRESS = 'in_progress', 'En cours'
        CLOSED      = 'closed',      'Clôturée'

    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='nonconformities',
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=Severity.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    procedure = models.ForeignKey(
        Procedure,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='nonconformities',
    )
    reported_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='reported_ncs',
    )
    assigned_to = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_ncs',
    )
    due_date = models.DateField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='closed_ncs',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Non-conformité'
        verbose_name_plural = 'Non-conformités'
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class CorrectiveAction(models.Model):
    nonconformity = models.ForeignKey(
        NonConformity,
        on_delete=models.CASCADE,
        related_name='corrective_actions',
    )
    description = models.TextField()
    responsible = models.ForeignKey(
        'team.Collaborator',
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='corrective_actions',
    )
    due_date = models.DateField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Action corrective'
        verbose_name_plural = 'Actions correctives'
        ordering = ['created_at']

    def __str__(self):
        return f"Action pour : {self.nonconformity}"
