# PROMPT — Validation Email (Le Lien Officinal)

## Contexte projet

Tu travailles sur **Le Lien Officinal** (`lienofficinal.fr`), un SaaS B2B Django REST Framework + Angular 18 pour pharmacies françaises.

- Stack backend : Django REST Framework, PostgreSQL, Redis, Celery, Mailgun EU (`mg.lienofficinal.fr`)
- Stack frontend : Angular 18 standalone components, Tailwind CSS, `inject()` systématiquement (pas de `constructor` injection)
- Authentification : JWT custom (PyJWT direct, **pas** SIMPLE_JWT)
- Deux types d'utilisateurs : `apps.core.Pharmacy` (titulaire) et `apps.team.Collaborator` (membres d'équipe)
- Les deux modèles ont un champ `email` de connexion
- Palette UI : **vert uniquement** (`green-700` principal) — aucun indigo, aucun bleu sauf données collaborateurs

---

## Étape 0 — AUDIT OBLIGATOIRE (ne rien modifier)

Avant toute modification, génère un rapport d'audit couvrant :

1. **`apps/core/models.py`** — champs existants sur `Pharmacy`, méthode `__str__`, Meta
2. **`apps/team/models.py`** — champs existants sur `Collaborator`, méthode `__str__`, Meta
3. **`apps/auth/` ou équivalent** — liste des views, serializers, urls existants liés à l'authentification
4. **Migrations existantes** — dernière migration de `core` et `team` (numéro + nom)
5. **Helper email existant** — existe-t-il déjà un utilitaire d'envoi Mailgun ? Si oui, chemin et signature
6. **`settings.py`** — variables d'environnement liées à Mailgun déjà déclarées
7. **Celery** — existe-t-il déjà un fichier `tasks.py` dans `apps/auth/` ou ailleurs ? Lister les tasks existantes
8. **Frontend `auth.service.ts`** — méthodes existantes, shape du payload JWT décodé, stockage du token, utilisation de `inject()` vs constructeur
9. **Routing Angular** — liste des routes existantes dans `app.routes.ts` ou équivalent

Ne touche à aucun fichier. Rapport uniquement.

---

## Étape 1 — Backend : Modèles

### 1a. Champs à ajouter sur `apps/core/models.py` → `Pharmacy`

```python
email_verified = models.BooleanField(default=False)
email_verification_token = models.CharField(max_length=64, blank=True, default='')
token_created_at = models.DateTimeField(null=True, blank=True)
```

### 1b. Champs identiques sur `apps/team/models.py` → `Collaborator`

```python
email_verified = models.BooleanField(default=False)
email_verification_token = models.CharField(max_length=64, blank=True, default='')
token_created_at = models.DateTimeField(null=True, blank=True)
```

### 1c. Migrations

Générer les migrations **avec un index sur `email_verification_token`** pour éviter un full scan lors de la vérification :

```python
# Dans chaque migration générée, ajouter dans operations[] :
models.AddIndex(
    model_name='pharmacy',  # ou 'collaborator'
    index=models.Index(
        fields=['email_verification_token'],
        name='pharmacy_email_verif_token_idx'  # adapter le nom
    ),
)
```

```bash
python manage.py makemigrations core --name="add_email_verification_fields"
python manage.py makemigrations team --name="add_email_verification_fields"
python manage.py migrate
```

---

## Étape 2 — Backend : Helper token + task Celery

### 2a. Utilitaire token

Crée ou enrichis `apps/auth/utils.py` :

```python
import secrets
from django.utils import timezone

TOKEN_EXPIRY_HOURS = 24

def generate_verification_token() -> str:
    """Génère un token hex de 32 bytes (64 chars). Compatible max_length=64."""
    return secrets.token_hex(32)

def is_token_valid(token_created_at) -> bool:
    """Retourne True si le token a moins de 24h."""
    if not token_created_at:
        return False
    delta = timezone.now() - token_created_at
    return delta.total_seconds() < TOKEN_EXPIRY_HOURS * 3600
```

### 2b. Helper envoi email Mailgun

Si un helper Mailgun existe déjà, étends-le. Sinon crée `apps/auth/email.py` :

```python
import requests
from django.conf import settings

def send_verification_email(email: str, token: str, user_type: str):
    """
    Envoie l'email de vérification via Mailgun EU.
    user_type : 'pharmacy' | 'collaborator'
    NE PAS appeler directement depuis une view — utiliser la task Celery.
    """
    frontend_url = settings.FRONTEND_BASE_URL
    verify_url = f"{frontend_url}/verify-email?token={token}&type={user_type}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 32px; color: #1a1a2e;">
      <img src="https://lienofficinal.fr/assets/logo.png" alt="Le Lien Officinal" style="height: 40px; margin-bottom: 24px;" />
      <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 8px;">Confirmez votre adresse email</h1>
      <p style="color: #555; margin-bottom: 24px;">
        Bienvenue sur Le Lien Officinal. Cliquez sur le bouton ci-dessous pour activer votre compte.
        Ce lien est valable <strong>24 heures</strong>.
      </p>
      <a href="{verify_url}"
         style="display: inline-block; background: #15803d; color: white; padding: 14px 28px;
                border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
        Vérifier mon email
      </a>
      <p style="margin-top: 24px; font-size: 13px; color: #999;">
        Si vous n'avez pas créé de compte, ignorez cet email.<br/>
        Ou copiez ce lien dans votre navigateur : {verify_url}
      </p>
      <hr style="margin-top: 40px; border: none; border-top: 1px solid #eee;" />
      <p style="font-size: 12px; color: #bbb;">Le Lien Officinal — lienofficinal.fr</p>
    </body>
    </html>
    """

    response = requests.post(
        f"https://api.eu.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages",
        auth=("api", settings.MAILGUN_API_KEY),
        data={
            "from": f"Le Lien Officinal <noreply@{settings.MAILGUN_DOMAIN}>",
            "to": email,
            "subject": "Confirmez votre adresse email — Le Lien Officinal",
            "html": html_content,
        }
    )
    response.raise_for_status()
    return response
```

### 2c. Task Celery

Dans `apps/auth/tasks.py` (créer si inexistant, sinon enrichir) :

```python
from celery import shared_task
from .email import send_verification_email as _send

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_verification_email_task(self, email: str, token: str, user_type: str):
    """
    Envoie l'email de vérification de manière asynchrone.
    Retry automatique x3 en cas d'échec Mailgun.
    """
    try:
        _send(email, token, user_type)
    except Exception as exc:
        raise self.retry(exc=exc)
```

> **Toujours appeler `send_verification_email_task.delay(...)` depuis les views, jamais `_send()` directement.**

### 2d. Variables `settings.py` à vérifier / ajouter

```python
MAILGUN_API_KEY = env("MAILGUN_API_KEY")
MAILGUN_DOMAIN = env("MAILGUN_DOMAIN", default="mg.lienofficinal.fr")
FRONTEND_BASE_URL = env("FRONTEND_BASE_URL", default="https://app.lienofficinal.fr")
```

---

## Étape 3 — Backend : Views + URLs

### 3a. Endpoint de vérification

Dans `apps/auth/views.py`, ajoute :

```python
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from .utils import is_token_valid

class VerifyEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token", "").strip()
        user_type = request.data.get("type", "").strip()

        if not token or user_type not in ("pharmacy", "collaborator"):
            return Response(
                {"detail": "Paramètres invalides."},
                status=status.HTTP_400_BAD_REQUEST
            )

        Model = Pharmacy if user_type == "pharmacy" else Collaborator

        try:
            user = Model.objects.get(email_verification_token=token)
        except Model.DoesNotExist:
            return Response(
                {"detail": "Token invalide ou déjà utilisé."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.email_verified:
            return Response({"detail": "Email déjà vérifié."}, status=status.HTTP_200_OK)

        if not is_token_valid(user.token_created_at):
            return Response(
                {"detail": "Lien expiré. Demandez un nouveau lien de vérification."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.email_verified = True
        user.email_verification_token = ""
        user.token_created_at = None
        user.save(update_fields=["email_verified", "email_verification_token", "token_created_at"])

        return Response({"detail": "Email vérifié avec succès."}, status=status.HTTP_200_OK)
```

### 3b. Endpoint renvoi d'email

```python
from rest_framework.throttling import UserRateThrottle
from .tasks import send_verification_email_task
from .utils import generate_verification_token

class ResendVerificationThrottle(UserRateThrottle):
    rate = '3/hour'

class ResendVerificationEmailView(APIView):
    """Accessible uniquement si authentifié mais email non vérifié."""
    # ⚠️ Adapter la permission selon le système JWT existant (voir audit Étape 0)
    permission_classes = [IsAuthenticated]
    throttle_classes = [ResendVerificationThrottle]

    def post(self, request):
        # ⚠️ Adapter selon request.pharmacy / request.collaborator selon le middleware JWT existant
        user = getattr(request, "pharmacy", None) or getattr(request, "collaborator", None)
        user_type = "pharmacy" if getattr(request, "pharmacy", None) else "collaborator"

        if not user:
            return Response({"detail": "Non authentifié."}, status=status.HTTP_401_UNAUTHORIZED)

        if user.email_verified:
            return Response({"detail": "Email déjà vérifié."}, status=status.HTTP_200_OK)

        token = generate_verification_token()
        user.email_verification_token = token
        user.token_created_at = timezone.now()
        user.save(update_fields=["email_verification_token", "token_created_at"])

        send_verification_email_task.delay(user.email, token, user_type)

        return Response({"detail": "Email de vérification renvoyé."}, status=status.HTTP_200_OK)
```

### 3c. Envoyer l'email à la création de compte

Dans la view existante de création de compte (Pharmacy ou Collaborator), après `instance.save()` :

```python
from apps.auth.utils import generate_verification_token
from apps.auth.tasks import send_verification_email_task
from django.utils import timezone

token = generate_verification_token()
instance.email_verification_token = token
instance.token_created_at = timezone.now()
instance.save(update_fields=["email_verification_token", "token_created_at"])
send_verification_email_task.delay(instance.email, token, "pharmacy")  # ou "collaborator"
```

### 3d. URLs

Dans `apps/auth/urls.py`, ajouter :

```python
path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
path("resend-verification/", ResendVerificationEmailView.as_view(), name="resend-verification"),
```

---

## Étape 4 — Backend : Permission DRF

Crée ou enrichis `apps/auth/permissions.py` :

```python
from rest_framework.permissions import BasePermission, SAFE_METHODS

class IsEmailVerified(BasePermission):
    """
    Autorise GET/HEAD/OPTIONS pour tous les utilisateurs authentifiés.
    Bloque POST/PUT/PATCH/DELETE si email non vérifié.
    """
    message = "Veuillez vérifier votre adresse email pour effectuer cette action."

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        # ⚠️ Adapter selon la shape de request dans le projet (voir audit Étape 0)
        user = getattr(request, "pharmacy", None) or getattr(request, "collaborator", None)
        if not user:
            return False
        return getattr(user, "email_verified", False)
```

> Appliquer `IsEmailVerified` sur les ViewSets concernés (Planning, Quality, Tasks, Messagerie) **après** la permission d'authentification existante.

---

## Étape 5 — Frontend Angular

### 5a. Mettre à jour `AuthService`

Dans `auth.service.ts`, vérifier que le payload JWT décodé expose `email_verified`. Si ce n'est pas le cas, ajouter `email_verified` dans la réponse de login côté backend.

> **Point critique** : après vérification de l'email, le JWT en cours ne se met **pas** à jour automatiquement. Deux approches possibles — choisir selon l'implémentation existante (voir audit) :
> - Option A : appeler le refresh token endpoint après vérification pour obtenir un nouveau JWT avec `email_verified: true`
> - Option B : lire `email_verified` depuis `GET /api/pharmacy/me/` plutôt que depuis le JWT décodé

Ajouter dans `AuthService` (utiliser `inject()`, pas de constructor injection) :

```typescript
get isEmailVerified(): boolean {
  const user = this.currentUser(); // adapter selon signal/BehaviorSubject existant
  return user?.email_verified ?? false;
}

verifyEmail(token: string, type: string): Observable<any> {
  return this.http.post(`${this.apiUrl}/auth/verify-email/`, { token, type });
}

resendVerification(): Observable<any> {
  return this.http.post(`${this.apiUrl}/auth/resend-verification/`, {});
}
```

### 5b. Page de vérification

Crée `src/app/features/verify-email/verify-email.component.ts` :

```typescript
import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/auth/auth.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="min-h-screen flex items-center justify-center bg-gray-50">
      <div class="bg-white rounded-2xl shadow-sm border border-gray-100 p-10 max-w-md w-full text-center">
        @if (status() === 'loading') {
          <div class="text-gray-500">Vérification en cours…</div>
        }
        @if (status() === 'success') {
          <div class="text-green-700 font-semibold text-lg">Email vérifié avec succès !</div>
          <p class="text-gray-500 mt-2 text-sm">Vous pouvez maintenant utiliser toutes les fonctionnalités.</p>
          <button (click)="goToDashboard()"
            class="mt-6 bg-green-700 text-white px-6 py-2 rounded-lg text-sm font-medium hover:bg-green-800 transition">
            Accéder au tableau de bord
          </button>
        }
        @if (status() === 'error') {
          <div class="text-red-600 font-semibold text-lg">Lien invalide ou expiré</div>
          <p class="text-gray-500 mt-2 text-sm">{{ errorMessage() }}</p>
        }
      </div>
    </div>
  `
})
export class VerifyEmailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private auth = inject(AuthService);

  status = signal<'loading' | 'success' | 'error'>('loading');
  errorMessage = signal('');

  ngOnInit() {
    const token = this.route.snapshot.queryParamMap.get('token') ?? '';
    const type = this.route.snapshot.queryParamMap.get('type') ?? '';

    this.auth.verifyEmail(token, type).subscribe({
      next: () => this.status.set('success'),
      error: (err) => {
        this.status.set('error');
        this.errorMessage.set(err?.error?.detail ?? 'Une erreur est survenue.');
      }
    });
  }

  goToDashboard() {
    this.router.navigate(['/dashboard']);
  }
}
```

### 5c. Bandeau d'alerte persistant

Crée `src/app/shared/components/email-banner/email-banner.component.ts` :

```typescript
import { Component, inject, signal } from '@angular/core';
import { AuthService } from '../../../core/auth/auth.service';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-email-banner',
  standalone: true,
  imports: [CommonModule],
  template: `
    @if (!auth.isEmailVerified && !dismissed()) {
      <div class="bg-amber-50 border-b border-amber-200 px-4 py-2 flex items-center justify-between text-sm">
        <span class="text-amber-800">
          Votre adresse email n'est pas encore vérifiée. Certaines actions sont désactivées.
        </span>
        <div class="flex items-center gap-3">
          <button (click)="resend()" [disabled]="sending()"
            class="text-green-700 font-medium hover:underline disabled:opacity-50">
            {{ sending() ? 'Envoi…' : 'Renvoyer l\'email' }}
          </button>
          <button (click)="dismissed.set(true)" class="text-amber-500 hover:text-amber-700">✕</button>
        </div>
      </div>
    }
  `
})
export class EmailBannerComponent {
  auth = inject(AuthService);
  dismissed = signal(false);
  sending = signal(false);

  resend() {
    this.sending.set(true);
    this.auth.resendVerification().subscribe({
      next: () => this.sending.set(false),
      error: () => this.sending.set(false)
    });
  }
}
```

Intégrer `<app-email-banner />` dans le layout principal (ex: `app-shell.component.html`), juste après la navbar.

### 5d. Route Angular

Dans `app.routes.ts`, ajouter :

```typescript
{
  path: 'verify-email',
  loadComponent: () =>
    import('./features/verify-email/verify-email.component').then(m => m.VerifyEmailComponent)
}
```

---

## Ordre d'exécution

1. Étape 0 — Audit (rapport, aucune modif)
2. Étape 1 — Migrations modèles (avec index)
3. Étape 2 — Helper token + helper email + task Celery
4. Étape 3 — Views + URLs + déclenchement à la création
5. Étape 4 — Permission DRF
6. Étape 5 — Frontend (service → page → bandeau → route)

---

## Points d'adaptation obligatoires (à résoudre à l'audit)

| Point | À vérifier |
|---|---|
| `request.pharmacy` vs `request.collaborator` | Dépend du middleware JWT existant |
| Payload JWT `email_verified` | Ajouter dans la réponse de login ; gérer le refresh après vérification (Option A ou B) |
| View de création de compte | Identifier la view existante pour y brancher `send_verification_email_task.delay()` |
| `IsAuthenticated` custom | Utiliser la permission existante du projet |
| `FRONTEND_BASE_URL` | Ajouter dans `.env` local et variables Scalingo |
| Task Celery | Vérifier que `celery.py` ou `__init__.py` expose bien `app` pour que `@shared_task` fonctionne |
