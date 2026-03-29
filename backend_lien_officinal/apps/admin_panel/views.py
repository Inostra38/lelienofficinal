import base64
import io
import time
from datetime import datetime, timezone, timedelta

import jwt
import pyotp
import qrcode
from django.conf import settings
from django.utils import timezone as django_tz
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import status

from .authentication import AdminJWTAuthentication
from .models import AdminUser
from .crypto import decrypt_totp_secret, encrypt_totp_secret

# Durées des tokens admin (indépendants de SIMPLE_JWT)
_ACCESS_LIFETIME = timedelta(minutes=15)
_REFRESH_LIFETIME = timedelta(days=7)
_SESSION_LIFETIME = timedelta(minutes=5)

_ALGORITHM = 'HS256'


def _secret():
    return settings.SECRET_KEY


# ── Helpers JWT ──────────────────────────────────────────────────────────────

def _issue_session_token(admin_id: int) -> str:
    """JWT court (5 min) autorisant uniquement l'appel à totp-verify/."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        'type': 'admin_session',
        'sub': str(admin_id),  # PyJWT 2.x exige string pour sub
        'iat': now,
        'exp': now + _SESSION_LIFETIME,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _issue_access_token(admin_id: int) -> str:
    """JWT d'accès admin (15 min)."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        'type': 'admin',
        'sub': str(admin_id),
        'iat': now,
        'exp': now + _ACCESS_LIFETIME,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _issue_refresh_token(admin_id: int) -> str:
    """JWT de refresh admin (7 jours)."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        'type': 'admin_refresh',
        'sub': str(admin_id),
        'iat': now,
        'exp': now + _REFRESH_LIFETIME,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _decode_token(token: str, expected_type: str) -> dict:
    """Décode et valide un JWT admin. Lève jwt.PyJWTError si invalide."""
    payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
    if payload.get('type') != expected_type:
        raise jwt.InvalidTokenError('Wrong token type')
    return payload


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key='admin_refresh_token',
        value=token,
        max_age=int(_REFRESH_LIFETIME.total_seconds()),
        httponly=True,
        samesite='Strict',
        secure=not settings.DEBUG,
        path='/api/admin/auth/',
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key='admin_refresh_token',
        path='/api/admin/auth/',
    )


# ── Views ────────────────────────────────────────────────────────────────────

class AdminLoginView(APIView):
    """
    POST /api/admin/auth/login/
    Étape 1 : email + password → session_token (5 min).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = request.data.get('email', '').strip()
        password = request.data.get('password', '')

        try:
            admin = AdminUser.objects.get(email=email, is_active=True)
        except AdminUser.DoesNotExist:
            time.sleep(0.5)  # protection timing attack
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        if not admin.check_password(password):
            time.sleep(0.5)
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        session_token = _issue_session_token(admin.pk)
        return Response({
            'step': 'totp_required',
            'session_token': session_token,
            'totp_configured': bool(admin.totp_secret),
        })


class AdminTotpVerifyView(APIView):
    """
    POST /api/admin/auth/totp-verify/
    Étape 2 : session_token + totp_code → access_token + cookie refresh.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        session_token = request.data.get('session_token', '')
        totp_code = request.data.get('totp_code', '')

        # Vérifier le session_token
        try:
            payload = _decode_token(session_token, 'admin_session')
        except jwt.PyJWTError:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            admin = AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except AdminUser.DoesNotExist:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        # Vérifier le code TOTP
        if not admin.totp_secret:
            # TOTP pas encore configuré : on autorise le passage pour le setup initial
            # (protégé côté endpoint setup par le token d'accès)
            pass
        else:
            raw_secret = decrypt_totp_secret(admin.totp_secret)
            totp = pyotp.TOTP(raw_secret)
            if not totp.verify(totp_code, valid_window=1):
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        # Émettre les tokens
        access_token = _issue_access_token(admin.pk)
        refresh_token = _issue_refresh_token(admin.pk)

        # Mettre à jour last_login
        admin.last_login_at = django_tz.now()
        admin.last_login_ip = _get_ip(request)
        admin.save(update_fields=['last_login_at', 'last_login_ip'])

        response = Response({'access_token': access_token})
        _set_refresh_cookie(response, refresh_token)
        return response


class AdminTokenRefreshView(APIView):
    """
    POST /api/admin/auth/refresh/
    Renouvelle l'access token depuis le cookie HttpOnly.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = request.COOKIES.get('admin_refresh_token', '')
        if not refresh_token:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            payload = _decode_token(refresh_token, 'admin_refresh')
        except jwt.PyJWTError:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            admin = AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except AdminUser.DoesNotExist:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        access_token = _issue_access_token(admin.pk)
        new_refresh_token = _issue_refresh_token(admin.pk)

        response = Response({'access_token': access_token})
        _set_refresh_cookie(response, new_refresh_token)
        return response


class AdminLogoutView(APIView):
    """
    POST /api/admin/auth/logout/
    Efface le cookie refresh (le token access expire naturellement après 15 min).
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        response = Response(status=status.HTTP_204_NO_CONTENT)
        _clear_refresh_cookie(response)
        return response


class AdminTotpSetupView(APIView):
    """
    GET  /api/admin/auth/totp-setup/
    Protégé : token admin valide + totp_secret vide (setup initial uniquement).
    Génère un secret et retourne l'otpauth_url, le secret brut et le QR en base64 PNG.
    Le secret N'EST PAS encore sauvegardé — il le sera après confirmation.
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        admin: AdminUser = request.user
        if admin.totp_secret:
            return Response(
                {'detail': 'TOTP déjà configuré.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        otpauth_url = totp.provisioning_uri(
            name=admin.email,
            issuer_name='Le Lien Officinal Admin',
        )

        # Générer le QR code en PNG base64
        img = qrcode.make(otpauth_url)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return Response({
            'otpauth_url': otpauth_url,
            'secret': secret,
            'qr_base64': qr_base64,
        })


class AdminTotpSetupConfirmView(APIView):
    """
    POST /api/admin/auth/totp-setup/confirm/
    Reçoit { totp_code } + le secret brut généré côté client (dans la session du setup).
    Vérifie le code, puis sauvegarde le secret chiffré.
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        admin: AdminUser = request.user
        if admin.totp_secret:
            return Response(
                {'detail': 'TOTP déjà configuré.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        totp_code = request.data.get('totp_code', '')
        secret = request.data.get('secret', '')

        if not secret or not totp_code:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(secret)
        if not totp.verify(totp_code, valid_window=1):
            return Response(
                {'detail': 'Code incorrect ou expiré.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        admin.totp_secret = encrypt_totp_secret(secret)
        admin.save(update_fields=['totp_secret'])

        return Response({'detail': 'TOTP configuré avec succès.'})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
