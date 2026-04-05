from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class AdminUserManager(BaseUserManager):
    ALLOWED_DOMAIN = 'lienofficinal.fr'

    def create_admin(self, email, password, **extra):
        email = self.normalize_email(email)
        domain = email.split('@')[-1].lower()
        if domain != self.ALLOWED_DOMAIN:
            raise ValueError(f"Seuls les emails @{self.ALLOWED_DOMAIN} sont autorisés pour les comptes admin.")
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class AdminUser(AbstractBaseUser):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=100)
    totp_secret = models.CharField(max_length=200, blank=True)  # chiffré via Fernet (~120 chars)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    force_password_change = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    objects = AdminUserManager()

    class Meta:
        app_label = 'admin_panel'

    def __str__(self):
        return self.email


class AdminAuditLog(models.Model):
    """
    Journal d'audit persistant des actions admin.
    Interrogeable via l'ORM et l'interface Django admin (en dev).
    """
    ACTION_CHOICES = [
        ('LOGIN_OK', 'Connexion réussie'),
        ('LOGIN_FAIL', 'Connexion échouée'),
        ('LOGOUT', 'Déconnexion'),
        ('PASSWORD_CHANGE', 'Changement de mot de passe'),
        ('TOTP_SETUP', 'Configuration TOTP'),
        ('RESOURCE_CREATE', 'Création ressource'),
        ('RESOURCE_UPDATE', 'Modification ressource'),
        ('RESOURCE_DELETE', 'Suppression ressource'),
        ('ITEM_CREATE', 'Ajout item'),
        ('ITEM_DELETE', 'Suppression item'),
        ('RECOMMEND_APPROVE', 'Approbation recommandation'),
        ('RECOMMEND_REJECT', 'Rejet recommandation'),
    ]

    admin = models.ForeignKey(
        AdminUser, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    detail = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'admin_panel'
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.created_at:%Y-%m-%d %H:%M}] {self.get_action_display()} — {self.admin or 'unknown'}"
