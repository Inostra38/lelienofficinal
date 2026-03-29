from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models


class AdminUserManager(BaseUserManager):
    def create_admin(self, email, password, **extra):
        user = self.model(email=self.normalize_email(email), **extra)
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
