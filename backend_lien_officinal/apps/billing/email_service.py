import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BILLING_FROM = f'Le Lien Officinal <facturation@{settings.MAILGUN_DOMAIN}>'


def _send_email(
    to: str,
    subject: str,
    html: str,
    text: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
) -> bool:
    """
    Envoie un email via Mailgun EU (même pattern que apps/core/email.py).
    Retourne True si succès, False sinon.
    """
    data = {
        'from':    BILLING_FROM,
        'to':      to,
        'subject': subject,
        'text':    text,
        'html':    html,
    }

    files = []
    if attachment_bytes and attachment_filename:
        files.append(
            ('attachment', (attachment_filename, attachment_bytes, 'application/pdf'))
        )

    try:
        response = requests.post(
            f'https://api.eu.mailgun.net/v3/{settings.MAILGUN_DOMAIN}/messages',
            auth=('api', settings.MAILGUN_API_KEY),
            data=data,
            files=files if files else None,
        )
        response.raise_for_status()
        logger.info('Email billing envoyé à %s — sujet : %s', to, subject)
        return True

    except requests.exceptions.RequestException as exc:
        logger.error('Mailgun billing erreur : %s', exc)
        return False


# ------------------------------------------------------------------ #
# Email 1 : Facture abonnement                                        #
# ------------------------------------------------------------------ #

def send_subscription_invoice_email(
    pharmacy,
    invoice,
    pdf_bytes: bytes,
    download_url: str,
) -> bool:
    """
    Envoie la facture d'abonnement avec :
    - PDF en pièce jointe
    - Lien de téléchargement signé (valable 10 min en prod)
    """
    subject = f'Votre facture Le Lien Officinal — {invoice.invoice_number}'

    plan_label = (
        'Small (< 10 collaborateurs)' if getattr(pharmacy, 'subscription', None)
        and pharmacy.subscription.plan == 'small'
        else 'Large (≥ 10 collaborateurs)'
    )

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 24px;">

      <div style="border-bottom: 3px solid #15803d; padding-bottom: 16px; margin-bottom: 24px;">
        <h1 style="color: #15803d; font-size: 20px; margin: 0;">Le Lien Officinal</h1>
      </div>

      <p style="font-size: 15px;">Bonjour,</p>

      <p>Votre facture <strong>{invoice.invoice_number}</strong> est disponible.</p>

      <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 24px 0;">
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">Plan</td>
            <td style="font-weight: bold; text-align: right;">{plan_label}</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">Montant HT</td>
            <td style="text-align: right;">{invoice.amount_ht} €</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">TVA ({invoice.tva_rate}%)</td>
            <td style="text-align: right;">
              {round(float(invoice.amount_ttc) - float(invoice.amount_ht), 2)} €
            </td>
          </tr>
          <tr style="border-top: 1px solid #e5e7eb;">
            <td style="font-weight: bold; color: #15803d; padding-top: 8px;">Total TTC</td>
            <td style="font-weight: bold; color: #15803d; text-align: right; padding-top: 8px;">
              {invoice.amount_ttc} €
            </td>
          </tr>
        </table>
      </div>

      <p style="font-size: 14px; color: #6b7280;">
        La facture est jointe à cet email en PDF.<br>
        Vous pouvez également la télécharger via le lien ci-dessous
        (valable 10 minutes) :
      </p>

      <div style="text-align: center; margin: 24px 0;">
        <a href="{download_url}"
           style="background: #15803d; color: white; padding: 12px 24px;
                  border-radius: 6px; text-decoration: none; font-weight: bold;
                  font-size: 14px;">
          Télécharger la facture PDF
        </a>
      </div>

      <p style="font-size: 13px; color: #9ca3af;">
        Retrouvez toutes vos factures dans votre espace client,
        rubrique <strong>Compte → Facturation</strong>.
      </p>

      <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px;
                  font-size: 11px; color: #d1d5db;">
        Le Lien Officinal SAS — contact@lienofficinal.fr — lienofficinal.fr<br>
        Cet email est envoyé automatiquement, merci de ne pas y répondre.
      </div>

    </body>
    </html>
    """

    text = (
        f"Bonjour,\n\n"
        f"Votre facture {invoice.invoice_number} est disponible.\n"
        f"Montant TTC : {invoice.amount_ttc} €\n\n"
        f"Téléchargez votre facture : {download_url}\n\n"
        f"Le Lien Officinal"
    )

    return _send_email(
        to=pharmacy.email,
        subject=subject,
        html=html,
        text=text,
        attachment_bytes=pdf_bytes,
        attachment_filename=f'{invoice.invoice_number}.pdf',
    )


# ------------------------------------------------------------------ #
# Email 2 : Reçu pack SMS                                             #
# ------------------------------------------------------------------ #

def send_sms_receipt_email(
    pharmacy,
    invoice,
    sms_quantity: int,
    pdf_bytes: bytes,
    download_url: str,
) -> bool:
    """
    Envoie le reçu pack SMS avec PDF joint + lien signé.
    """
    subject = f'Votre reçu pack SMS — {invoice.invoice_number}'

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 24px;">

      <div style="border-bottom: 3px solid #15803d; padding-bottom: 16px; margin-bottom: 24px;">
        <h1 style="color: #15803d; font-size: 20px; margin: 0;">Le Lien Officinal</h1>
      </div>

      <p style="font-size: 15px;">Bonjour,</p>

      <p>Votre achat de <strong>{sms_quantity} SMS</strong> a bien été enregistré.</p>

      <div style="background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
                  padding: 16px; margin: 24px 0;">
        <table style="width: 100%; font-size: 14px; border-collapse: collapse;">
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">Pack acheté</td>
            <td style="font-weight: bold; text-align: right;">{sms_quantity} SMS</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">Montant HT</td>
            <td style="text-align: right;">{invoice.amount_ht} €</td>
          </tr>
          <tr>
            <td style="color: #6b7280; padding: 4px 0;">TVA ({invoice.tva_rate}%)</td>
            <td style="text-align: right;">
              {round(float(invoice.amount_ttc) - float(invoice.amount_ht), 2)} €
            </td>
          </tr>
          <tr style="border-top: 1px solid #e5e7eb;">
            <td style="font-weight: bold; color: #15803d; padding-top: 8px;">Total TTC</td>
            <td style="font-weight: bold; color: #15803d; text-align: right; padding-top: 8px;">
              {invoice.amount_ttc} €
            </td>
          </tr>
        </table>
      </div>

      <p style="font-size: 14px; color: #6b7280;">
        Le reçu est joint à cet email en PDF.<br>
        Vous pouvez également le télécharger via le lien ci-dessous
        (valable 10 minutes) :
      </p>

      <div style="text-align: center; margin: 24px 0;">
        <a href="{download_url}"
           style="background: #15803d; color: white; padding: 12px 24px;
                  border-radius: 6px; text-decoration: none; font-weight: bold;
                  font-size: 14px;">
          Télécharger le reçu PDF
        </a>
      </div>

      <p style="font-size: 13px; color: #9ca3af;">
        Vos crédits SMS ont été crédités immédiatement sur votre compte.<br>
        Retrouvez votre solde dans <strong>Compte → Facturation</strong>.
      </p>

      <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px;
                  font-size: 11px; color: #d1d5db;">
        Le Lien Officinal SAS — contact@lienofficinal.fr — lienofficinal.fr<br>
        Cet email est envoyé automatiquement, merci de ne pas y répondre.
      </div>

    </body>
    </html>
    """

    text = (
        f"Bonjour,\n\n"
        f"Votre achat de {sms_quantity} SMS a bien été enregistré.\n"
        f"Montant TTC : {invoice.amount_ttc} €\n\n"
        f"Téléchargez votre reçu : {download_url}\n\n"
        f"Le Lien Officinal"
    )

    return _send_email(
        to=pharmacy.email,
        subject=subject,
        html=html,
        text=text,
        attachment_bytes=pdf_bytes,
        attachment_filename=f'{invoice.invoice_number}.pdf',
    )


# ------------------------------------------------------------------ #
# Email 3 : Fin de trial J-3                                          #
# ------------------------------------------------------------------ #

def send_trial_ending_email(pharmacy) -> bool:
    subject = 'Votre essai Le Lien Officinal se termine bientôt'

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 24px;">

      <div style="border-bottom: 3px solid #15803d; padding-bottom: 16px; margin-bottom: 24px;">
        <h1 style="color: #15803d; font-size: 20px; margin: 0;">Le Lien Officinal</h1>
      </div>

      <p style="font-size: 15px;">Bonjour,</p>

      <p>Votre période d'essai gratuite se termine dans <strong>3 jours</strong>.</p>

      <p style="color: #4b5563;">
        Pour continuer à bénéficier de Le Lien Officinal sans interruption,
        configurez votre prélèvement SEPA dès maintenant.
      </p>

      <div style="text-align: center; margin: 32px 0;">
        <a href="{settings.FRONTEND_BASE_URL}/account"
           style="background: #15803d; color: white; padding: 14px 28px;
                  border-radius: 6px; text-decoration: none; font-weight: bold;
                  font-size: 15px;">
          Configurer mon abonnement
        </a>
      </div>

      <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px;
                  padding: 16px; margin: 24px 0; font-size: 14px;">
        <strong style="color: #15803d;">Votre tarif :</strong><br>
        39€/mois HT (&lt; 10 collaborateurs) ou 59€/mois HT (≥ 10 collaborateurs)<br>
        Tous les modules inclus — Planning CCN, Qualité, Tâches, Messagerie, IA
      </div>

      <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px;
                  font-size: 11px; color: #d1d5db;">
        Le Lien Officinal SAS — contact@lienofficinal.fr — lienofficinal.fr
      </div>

    </body>
    </html>
    """

    text = (
        "Bonjour,\n\n"
        "Votre période d'essai se termine dans 3 jours.\n"
        f"Configurez votre abonnement : {settings.FRONTEND_BASE_URL}/account\n\n"
        "Tarif : 39€/mois HT (< 10 collaborateurs) ou 59€/mois HT (≥ 10 collaborateurs)\n\n"
        "Le Lien Officinal"
    )

    return _send_email(
        to=pharmacy.email,
        subject=subject,
        html=html,
        text=text,
    )


# ------------------------------------------------------------------ #
# Email 4 : Relance impayé                                            #
# ------------------------------------------------------------------ #

def send_payment_failed_email(pharmacy) -> bool:
    subject = 'Action requise — Problème de paiement Le Lien Officinal'

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 24px;">

      <div style="border-bottom: 3px solid #dc2626; padding-bottom: 16px; margin-bottom: 24px;">
        <h1 style="color: #15803d; font-size: 20px; margin: 0;">Le Lien Officinal</h1>
      </div>

      <p style="font-size: 15px;">Bonjour,</p>

      <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px;
                  padding: 16px; margin: 16px 0;">
        <p style="color: #dc2626; font-weight: bold; margin: 0;">
          ⚠️ Votre prélèvement SEPA a échoué.
        </p>
      </div>

      <p style="color: #4b5563;">
        Votre accès à Le Lien Officinal sera suspendu dans <strong>7 jours</strong>
        si le paiement n'est pas régularisé.
      </p>

      <div style="text-align: center; margin: 32px 0;">
        <a href="{settings.FRONTEND_BASE_URL}/account"
           style="background: #dc2626; color: white; padding: 14px 28px;
                  border-radius: 6px; text-decoration: none; font-weight: bold;
                  font-size: 15px;">
          Régulariser mon paiement
        </a>
      </div>

      <p style="font-size: 13px; color: #9ca3af;">
        Si vous rencontrez des difficultés, contactez-nous à
        <a href="mailto:contact@lienofficinal.fr" style="color: #15803d;">
          contact@lienofficinal.fr
        </a>
      </p>

      <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px;
                  font-size: 11px; color: #d1d5db;">
        Le Lien Officinal SAS — contact@lienofficinal.fr — lienofficinal.fr
      </div>

    </body>
    </html>
    """

    text = (
        "Bonjour,\n\n"
        "Votre prélèvement SEPA a échoué.\n"
        "Votre accès sera suspendu dans 7 jours sans régularisation.\n\n"
        f"Régularisez ici : {settings.FRONTEND_BASE_URL}/account\n\n"
        "Le Lien Officinal"
    )

    return _send_email(
        to=pharmacy.email,
        subject=subject,
        html=html,
        text=text,
    )


# ------------------------------------------------------------------ #
# Email 5 : Suspension effective                                       #
# ------------------------------------------------------------------ #

def send_suspension_email(pharmacy) -> bool:
    subject = 'Votre accès Le Lien Officinal a été suspendu'

    html = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head><meta charset="UTF-8"></head>
    <body style="font-family: Arial, sans-serif; color: #1f2937; max-width: 600px; margin: 0 auto; padding: 24px;">

      <div style="border-bottom: 3px solid #dc2626; padding-bottom: 16px; margin-bottom: 24px;">
        <h1 style="color: #15803d; font-size: 20px; margin: 0;">Le Lien Officinal</h1>
      </div>

      <p style="font-size: 15px;">Bonjour,</p>

      <p>
        Votre accès à Le Lien Officinal a été <strong>suspendu</strong>
        suite à un impayé non régularisé.
      </p>

      <div style="text-align: center; margin: 32px 0;">
        <a href="{settings.FRONTEND_BASE_URL}/account"
           style="background: #15803d; color: white; padding: 14px 28px;
                  border-radius: 6px; text-decoration: none; font-weight: bold;
                  font-size: 15px;">
          Réactiver mon compte
        </a>
      </div>

      <p style="font-size: 13px; color: #9ca3af;">
        Vos données sont conservées et accessibles dès réactivation.<br>
        Contact : <a href="mailto:contact@lienofficinal.fr" style="color: #15803d;">
          contact@lienofficinal.fr
        </a>
      </p>

      <div style="border-top: 1px solid #e5e7eb; margin-top: 32px; padding-top: 16px;
                  font-size: 11px; color: #d1d5db;">
        Le Lien Officinal SAS — contact@lienofficinal.fr — lienofficinal.fr
      </div>

    </body>
    </html>
    """

    text = (
        "Bonjour,\n\n"
        "Votre accès a été suspendu suite à un impayé.\n"
        f"Réactivez votre compte : {settings.FRONTEND_BASE_URL}/account\n\n"
        "Le Lien Officinal"
    )

    return _send_email(
        to=pharmacy.email,
        subject=subject,
        html=html,
        text=text,
    )
