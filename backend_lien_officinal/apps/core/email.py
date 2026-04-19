import requests
from django.conf import settings


def send_email_change_confirmation(old_email: str, new_email: str, token: str):
    """
    Envoie le lien de confirmation au NOUVEL email.
    NE PAS appeler directement — utiliser send_email_change_task.delay().
    """
    confirm_url = f"{settings.FRONTEND_BASE_URL}/confirm-email-change?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 32px; color: #1a1a2e;">
      <img src="https://lienofficinal.fr/assets/logo.png" alt="Le Lien Officinal" style="height: 40px; margin-bottom: 24px;" />
      <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 8px;">Confirmez votre nouvel email</h1>
      <p style="color: #555; margin-bottom: 8px;">
        Vous avez demandé à changer votre adresse email sur Le Lien Officinal.
      </p>
      <p style="color: #555; margin-bottom: 24px;">
        Votre email actuel <strong>{old_email}</strong> reste actif jusqu'à confirmation.<br/>
        Ce lien est valable <strong>24 heures</strong>.
      </p>
      <a href="{confirm_url}"
         style="display: inline-block; background: #15803d; color: white; padding: 14px 28px;
                border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
        Confirmer mon nouvel email
      </a>
      <p style="margin-top: 24px; font-size: 13px; color: #999;">
        Si vous n'avez pas effectué cette demande, ignorez cet email — rien ne changera.<br/>
        Ou copiez ce lien dans votre navigateur : {confirm_url}
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
            "to": new_email,
            "subject": "Confirmez votre nouvel email — Le Lien Officinal",
            "html": html_content,
        }
    )
    response.raise_for_status()
    return response


def send_password_reset_email(email: str, token: str):
    """
    Envoie l'email de réinitialisation de mot de passe via Mailgun EU.
    NE PAS appeler directement — utiliser send_password_reset_task.delay().
    """
    reset_url = f"{settings.FRONTEND_BASE_URL}/reset-password?token={token}"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: sans-serif; max-width: 600px; margin: auto; padding: 32px; color: #1a1a2e;">
      <img src="https://lienofficinal.fr/assets/logo.png" alt="Le Lien Officinal" style="height: 40px; margin-bottom: 24px;" />
      <h1 style="font-size: 22px; font-weight: 700; margin-bottom: 8px;">Réinitialisation de votre mot de passe</h1>
      <p style="color: #555; margin-bottom: 24px;">
        Vous avez demandé à réinitialiser votre mot de passe sur Le Lien Officinal.<br/>
        Cliquez sur le bouton ci-dessous pour en choisir un nouveau.
        Ce lien est valable <strong>1 heure</strong> et à usage unique.
      </p>
      <a href="{reset_url}"
         style="display: inline-block; background: #15803d; color: white; padding: 14px 28px;
                border-radius: 8px; text-decoration: none; font-weight: 600; font-size: 15px;">
        Réinitialiser mon mot de passe
      </a>
      <p style="margin-top: 24px; font-size: 13px; color: #999;">
        Si vous n'avez pas effectué cette demande, ignorez cet email — votre mot de passe reste inchangé.<br/>
        Ou copiez ce lien dans votre navigateur : {reset_url}
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
            "subject": "Réinitialisation de votre mot de passe — Le Lien Officinal",
            "html": html_content,
        }
    )
    response.raise_for_status()
    return response


def send_verification_email(email: str, token: str):
    """
    Envoie l'email de vérification via Mailgun EU.
    NE PAS appeler directement depuis une view — utiliser send_verification_email_task.delay().
    """
    verify_url = f"{settings.FRONTEND_BASE_URL}/verify-email?token={token}"

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
