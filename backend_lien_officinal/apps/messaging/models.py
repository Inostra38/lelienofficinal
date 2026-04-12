import uuid
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from encrypted_model_fields.fields import EncryptedTextField


class Conversation(models.Model):
    """
    Fil de discussion entre membres d'une même pharmacie.
    Le scope pharmacie est assuré par la FK vers Pharmacy.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pharmacy = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations',
        verbose_name=_("Pharmacie")
    )
    subject = EncryptedTextField(_("Sujet"))
    created_by = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_conversations',
        verbose_name=_("Créé par")
    )
    participants = models.ManyToManyField(
        'team.Collaborator',
        related_name='conversations',
        blank=True,
        verbose_name=_("Participants")
    )
    hidden_by = models.ManyToManyField(
        'team.Collaborator',
        related_name='hidden_conversations',
        blank=True,
        verbose_name=_("Masquée par")
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Conversation")
        verbose_name_plural = _("Conversations")
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.subject} — {self.pharmacy}"


class Message(models.Model):
    """
    Message dans un fil de discussion.
    Le contenu est chiffré au repos via EncryptedTextField.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
        verbose_name=_("Conversation")
    )
    sender = models.ForeignKey(
        'team.Collaborator',
        on_delete=models.SET_NULL,
        null=True,
        related_name='sent_messages',
        verbose_name=_("Expéditeur")
    )
    # Chiffré au repos — clé dans FIELD_ENCRYPTION_KEY (settings)
    content = EncryptedTextField(_("Contenu"))
    is_read_by = models.ManyToManyField(
        'team.Collaborator',
        related_name='read_messages',
        blank=True,
        verbose_name=_("Lu par")
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Message")
        verbose_name_plural = _("Messages")
        ordering = ['created_at']

    def __str__(self):
        return f"Message de {self.sender} dans '{self.conversation.subject}'"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Met à jour updated_at de la conversation à chaque nouveau message
        self.conversation.save(update_fields=['updated_at'])
