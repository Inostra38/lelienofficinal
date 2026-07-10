import base64
import io
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta

import jwt
import pyotp
import qrcode
from django.conf import settings
from django.core.cache import cache, caches
from django.utils import timezone as django_tz
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from .authentication import AdminJWTAuthentication, is_jti_revoked
from .models import AdminUser, AdminAuditLog
from .crypto import decrypt_totp_secret, encrypt_totp_secret
from .serializers import ChangePasswordSerializer

logger = logging.getLogger(__name__)

# Durées des tokens admin (indépendants de SIMPLE_JWT)
_ACCESS_LIFETIME = timedelta(minutes=15)
_REFRESH_LIFETIME = timedelta(days=1)
_SESSION_LIFETIME = timedelta(minutes=5)

_ALGORITHM = 'HS256'


# ── Throttles admin ─────────────────────────────────────────────────────────

class AdminLoginThrottle(AnonRateThrottle):
    rate = '5/hour'

    def allow_request(self, request, view):
        if settings.DEBUG:
            return True
        return super().allow_request(request, view)


class AdminTotpThrottle(AnonRateThrottle):
    rate = '10/hour'

    def allow_request(self, request, view):
        if settings.DEBUG:
            return True
        return super().allow_request(request, view)


def _secret():
    # E1 : les JWT admin sont signés avec une clé dédiée, indépendante de
    # SECRET_KEY, pour qu'une fuite de SECRET_KEY ne permette pas de les forger.
    return settings.ADMIN_JWT_SECRET


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
    """JWT d'accès admin (15 min) avec jti pour révocation."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        'type': 'admin',
        'sub': str(admin_id),
        'jti': str(uuid.uuid4()),
        'iat': now,
        'exp': now + _ACCESS_LIFETIME,
    }
    return jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def _issue_refresh_token(admin_id: int) -> str:
    """JWT de refresh admin (1 jour) avec jti."""
    now = datetime.now(tz=timezone.utc)
    jti = str(uuid.uuid4())
    payload = {
        'type': 'admin_refresh',
        'sub': str(admin_id),
        'jti': jti,
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


def _blacklist_jti(payload: dict) -> None:
    """
    M4 : blackliste le jti d'un token jusqu'à son expiration (même namespace
    que la blacklist d'access token vérifiée dans AdminJWTAuthentication).
    Utilisé pour les access ET refresh tokens, au logout et à la rotation.
    """
    jti = payload.get('jti')
    if not jti:
        return
    ttl = int(payload.get('exp', 0) - datetime.now(tz=timezone.utc).timestamp())
    if ttl > 0:
        # S21 : la blacklist vit dans le cache dédié `admin_revocation` (Redis
        # natif, fail-closed à la lecture). Best-effort à l'écriture pour ne pas
        # faire échouer le logout si Redis tousse — durant l'indisponibilité la
        # lecture refuse de toute façon tous les tokens (fail-closed).
        try:
            caches['admin_revocation'].set(f"admin_blacklist_{jti}", True, timeout=ttl)
        except Exception:
            logger.warning("Blacklist admin : écriture Redis échouée (jti=%s)", jti, exc_info=True)


def _is_blacklisted(payload: dict) -> bool:
    return is_jti_revoked(payload.get('jti'))


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key='admin_refresh_token',
        value=token,
        max_age=int(_REFRESH_LIFETIME.total_seconds()),
        httponly=True,
        samesite='Strict' if not settings.DEBUG else 'Lax',
        secure=not settings.DEBUG,
        path='/api/admin/auth/',
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key='admin_refresh_token',
        path='/api/admin/auth/',
    )


def _audit(action: str, request, admin=None, detail: str = ''):
    """Enregistre une action dans le journal d'audit admin."""
    ip = _get_ip(request)
    if admin is None:
        # Sur les endpoints non authentifiés (login), request.user est un
        # AnonymousUser : le FK admin n'accepte qu'un AdminUser (ou None).
        user = getattr(request, 'user', None)
        admin = user if isinstance(user, AdminUser) else None
    AdminAuditLog.objects.create(
        admin=admin,
        action=action,
        detail=detail,
        ip_address=ip,
    )
    logger.info(f"AUDIT {action}: {detail} [admin={admin or 'unknown'}, ip={ip}]")


# ── Views ────────────────────────────────────────────────────────────────────

class AdminLoginView(APIView):
    """
    POST /api/admin/auth/login/
    Étape 1 : email + password → session_token (5 min).
    """
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AdminLoginThrottle]

    def post(self, request):
        email = request.data.get('email', '').strip().lower()
        password = request.data.get('password', '')

        try:
            admin = AdminUser.objects.get(email=email, is_active=True)
        except AdminUser.DoesNotExist:
            _audit('LOGIN_FAIL', request, detail=f"Unknown email: {email}")
            time.sleep(0.5)
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        if not admin.check_password(password):
            _audit('LOGIN_FAIL', request, admin=admin, detail=f"Wrong password for {email}")
            time.sleep(0.5)
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        _audit('LOGIN_OK', request, admin=admin, detail=f"Step 1 OK for {email}")
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
    throttle_classes = [AdminTotpThrottle]

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
            pass
        else:
            raw_secret = decrypt_totp_secret(admin.totp_secret)
            totp = pyotp.TOTP(raw_secret)
            if not totp.verify(totp_code, valid_window=1):
                _audit('LOGIN_FAIL', request, admin=admin, detail="TOTP code invalid")
                return Response(status=status.HTTP_401_UNAUTHORIZED)
            # Anti-replay TOTP (M5) : claim ATOMIQUE du code via cache.add, qui
            # renvoie False si la clé existe déjà → rejeu détecté sans course.
            # TTL ≥ fenêtre de validité (valid_window=1 ⇒ code accepté ~90 s).
            totp_key = f"totp_used_{admin.pk}_{totp_code}"
            if not cache.add(totp_key, True, timeout=90):
                _audit('LOGIN_FAIL', request, admin=admin, detail="TOTP replay detected")
                return Response(status=status.HTTP_401_UNAUTHORIZED)

        # Émettre les tokens
        access_token = _issue_access_token(admin.pk)
        refresh_token = _issue_refresh_token(admin.pk)

        # Mettre à jour last_login
        admin.last_login_at = django_tz.now()
        admin.last_login_ip = _get_ip(request)
        admin.save(update_fields=['last_login_at', 'last_login_ip'])
        _audit('LOGIN_OK', request, admin=admin, detail=f"Full login OK for {admin.email}")

        response = Response({
            'access_token': access_token,
            'force_password_change': admin.force_password_change,
            'totp_configured': bool(admin.totp_secret),
        })
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

        # M4 : un refresh révoqué (logout ou déjà tourné) ne doit plus servir.
        if _is_blacklisted(payload):
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            admin = AdminUser.objects.get(pk=int(payload['sub']), is_active=True)
        except AdminUser.DoesNotExist:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        # M4 : rotation — blacklister l'ancien refresh avant d'en émettre un
        # nouveau (un refresh ne peut être consommé qu'une fois).
        _blacklist_jti(payload)

        access_token = _issue_access_token(admin.pk)
        new_refresh_token = _issue_refresh_token(admin.pk)

        response = Response({'access_token': access_token})
        _set_refresh_cookie(response, new_refresh_token)
        return response


class AdminLogoutView(APIView):
    """
    POST /api/admin/auth/logout/
    Blackliste le token d'accès + efface le cookie refresh.
    """
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        # Blacklister l'access token en cours
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header.split(' ', 1)[1]
            try:
                payload = jwt.decode(token, _secret(), algorithms=[_ALGORITHM])
                _blacklist_jti(payload)
                _audit('LOGOUT', request, detail=f"Admin id={payload.get('sub')}")
            except jwt.PyJWTError:
                pass

        # M4 : blacklister AUSSI le refresh token du cookie (avant, il restait
        # valide ~24 h après le logout). On efface le cookie ET on révoque le jti.
        refresh_token = request.COOKIES.get('admin_refresh_token', '')
        if refresh_token:
            try:
                refresh_payload = jwt.decode(refresh_token, _secret(), algorithms=[_ALGORITHM])
                _blacklist_jti(refresh_payload)
            except jwt.PyJWTError:
                pass

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

        # Stocker le secret en cache (10 min TTL), PAS envoyé au frontend
        cache.set(f"totp_setup_{admin.pk}", secret, timeout=600)

        # Générer le QR code en PNG base64
        img = qrcode.make(otpauth_url)
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        qr_base64 = base64.b64encode(buffer.getvalue()).decode()

        return Response({
            'otpauth_url': otpauth_url,
            'qr_base64': qr_base64,
        })


class AdminTotpSetupConfirmView(APIView):
    """
    POST /api/admin/auth/totp-setup/confirm/
    Reçoit { totp_code } uniquement. Le secret est récupéré depuis le cache backend.
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
        if not totp_code:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Récupérer le secret depuis le cache (généré par GET /totp-setup/)
        secret = cache.get(f"totp_setup_{admin.pk}")
        if not secret:
            return Response(
                {'detail': 'Session TOTP expirée. Rechargez le QR code.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        totp = pyotp.TOTP(secret)
        if not totp.verify(totp_code, valid_window=1):
            return Response(
                {'detail': 'Code incorrect ou expiré.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        admin.totp_secret = encrypt_totp_secret(secret)
        admin.save(update_fields=['totp_secret'])
        cache.delete(f"totp_setup_{admin.pk}")
        _audit('TOTP_SETUP', request, admin=admin, detail="TOTP configured")

        return Response({'detail': 'TOTP configuré avec succès.'})


class AdminChangePasswordView(APIView):
    """
    POST /api/admin/auth/change-password/
    Changement de mot de passe admin (requis au premier login).
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        admin = request.user
        if not admin.check_password(serializer.validated_data['old_password']):
            return Response(
                {'old_password': 'Mot de passe actuel incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        admin.set_password(serializer.validated_data['new_password'])
        admin.force_password_change = False
        admin.save(update_fields=['password', 'force_password_change'])

        _audit('PASSWORD_CHANGE', request, admin=admin, detail="Password changed")
        return Response({'detail': 'Mot de passe modifié avec succès.'})


# ── Ressources (liste admin) ────────────────────────────────────────────────

from apps.resources.models import ResourceCard, ResourceItem
from .serializers import RecommendationCardSerializer, RecommendationItemSerializer
from django.db.models import Count, Q


class ListCreateResourceView(APIView):
    """
    GET  /api/admin/resources/         → liste toutes les ressources
    POST /api/admin/resources/         → crée une nouvelle ressource
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        limit = min(int(request.query_params.get('limit', 100)), 500)
        offset = int(request.query_params.get('offset', 0))

        qs = ResourceCard.objects.annotate(
            pharmacy_count=Count(
                'preferences',
                filter=Q(preferences__assigned_category__isnull=False),
                distinct=True,
            )
        ).order_by('-is_featured', 'titre')

        total = qs.count()
        cards = qs.values(
            'id', 'titre', 'description_officielle', 'type',
            'is_featured', 'pharmacy_count',
        )[offset:offset + limit]

        return Response({'count': total, 'results': list(cards)})

    def post(self, request):
        titre = request.data.get('titre', '').strip()
        if not titre:
            return Response({'error': 'Le titre est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)

        card = ResourceCard.objects.create(
            titre=titre,
            description_officielle=request.data.get('description_officielle', ''),
            type=request.data.get('type', 'OFFICIAL'),
            is_featured=request.data.get('is_featured', False),
        )
        _audit('RESOURCE_CREATE', request, detail=f"Created '{card.titre}' (id={card.id})")
        return Response({
            'id': card.id,
            'titre': card.titre,
            'description_officielle': card.description_officielle,
            'type': card.type,
            'is_featured': card.is_featured,
        }, status=status.HTTP_201_CREATED)


class ResourceDetailView(APIView):
    """
    GET    /api/admin/resources/<id>/  → détail avec items
    PATCH  /api/admin/resources/<id>/  → modification
    DELETE /api/admin/resources/<id>/  → suppression
    """
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, card_id):
        try:
            card = ResourceCard.objects.prefetch_related('items').get(pk=card_id)
        except ResourceCard.DoesNotExist:
            return Response({'error': 'Ressource non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        items = [
            {
                'id': item.id,
                'type': item.type,
                'label': item.label,
                'url': item.url,
                'file': item.file.url if item.file else None,
                'ordre': item.ordre,
            }
            for item in card.items.order_by('ordre', 'id')
        ]

        return Response({
            'id': card.id,
            'titre': card.titre,
            'description_officielle': card.description_officielle,
            'type': card.type,
            'is_featured': card.is_featured,
            'items': items,
        })

    def patch(self, request, card_id):
        try:
            card = ResourceCard.objects.get(pk=card_id)
        except ResourceCard.DoesNotExist:
            return Response({'error': 'Ressource non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        fields_to_update = []
        for field in ('titre', 'description_officielle', 'type', 'is_featured'):
            if field in request.data:
                setattr(card, field, request.data[field])
                fields_to_update.append(field)

        if fields_to_update:
            card.save(update_fields=fields_to_update)
            _audit('RESOURCE_UPDATE', request, detail=f"Updated '{card.titre}' (id={card.id}, fields={fields_to_update})")

        return Response({
            'id': card.id,
            'titre': card.titre,
            'description_officielle': card.description_officielle,
            'type': card.type,
            'is_featured': card.is_featured,
        })

    def delete(self, request, card_id):
        try:
            card = ResourceCard.objects.get(pk=card_id)
        except ResourceCard.DoesNotExist:
            return Response({'error': 'Ressource non trouvée'}, status=status.HTTP_404_NOT_FOUND)
        _audit('RESOURCE_DELETE', request, detail=f"Deleted '{card.titre}' (id={card_id})")
        card.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# M3 : validation factorisée dans apps.core.upload_validation (partagée avec
# les uploads côté pharmacie).
from apps.core.upload_validation import validate_upload as _validate_upload
from django.core.exceptions import ValidationError as _DjangoValidationError


class ResourceItemCreateView(APIView):
    """POST /api/admin/resources/<card_id>/items/  → ajouter un item"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        try:
            card = ResourceCard.objects.get(pk=card_id)
        except ResourceCard.DoesNotExist:
            return Response({'error': 'Ressource non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        label = request.data.get('label', '').strip()
        if not label:
            return Response({'error': 'Le label est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)

        # Validation fichier (M3 : helper partagé)
        uploaded = request.FILES.get('file')
        try:
            _validate_upload(uploaded)
        except _DjangoValidationError as e:
            return Response({'error': e.messages[0]}, status=status.HTTP_400_BAD_REQUEST)

        last_ordre = card.items.count()
        item = ResourceItem.objects.create(
            card=card,
            type=request.data.get('type', 'WEB'),
            label=label,
            url=request.data.get('url', ''),
            file=uploaded,
            ordre=last_ordre,
        )
        _audit('ITEM_CREATE', request, detail=f"Added item '{label}' to card '{card.titre}' (id={card_id})")
        return Response({
            'id': item.id,
            'type': item.type,
            'label': item.label,
            'url': item.url,
            'ordre': item.ordre,
        }, status=status.HTTP_201_CREATED)


class ResourceItemDeleteView(APIView):
    """DELETE /api/admin/resources/items/<item_id>/"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, item_id):
        try:
            item = ResourceItem.objects.get(pk=item_id)
        except ResourceItem.DoesNotExist:
            return Response({'error': 'Item non trouvé'}, status=status.HTTP_404_NOT_FOUND)
        _audit('ITEM_DELETE', request, detail=f"Deleted item '{item.label}' (id={item_id})")
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Recommandations communautaires ──────────────────────────────────────────


class ListRecommendationsView(APIView):
    """GET /api/admin/recommendations/?status=PENDING"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        status_filter = request.query_params.get('status', 'PENDING')

        cards_qs = ResourceCard.objects.filter(
            recommended_to_community=True,
        ).select_related('owner_pharmacy').prefetch_related('items')

        items_qs = ResourceItem.objects.filter(
            recommended_to_community=True,
        ).select_related('card', 'card__owner_pharmacy', 'target_official_card')

        if status_filter != 'ALL':
            cards_qs = cards_qs.filter(recommendation_status=status_filter)
            items_qs = items_qs.filter(recommendation_status=status_filter)

        cards_data = RecommendationCardSerializer(cards_qs.order_by('-recommended_at'), many=True).data
        items_data = RecommendationItemSerializer(items_qs.order_by('-recommended_at'), many=True).data

        return Response({
            'cards': cards_data,
            'items': items_data,
            'counts': {
                'pending_cards': ResourceCard.objects.filter(
                    recommended_to_community=True, recommendation_status='PENDING'
                ).count(),
                'pending_items': ResourceItem.objects.filter(
                    recommended_to_community=True, recommendation_status='PENDING'
                ).count(),
            }
        })


class ApproveCardView(APIView):
    """POST /api/admin/recommendations/card/<id>/approve/"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, card_id):
        try:
            card = ResourceCard.objects.get(pk=card_id, recommended_to_community=True)
        except ResourceCard.DoesNotExist:
            return Response({'error': 'Carte non trouvée'}, status=status.HTTP_404_NOT_FOUND)

        card.type = 'OFFICIAL'
        card.owner_pharmacy = None
        card.recommendation_status = 'APPROVED'
        card.save(update_fields=['type', 'owner_pharmacy', 'recommendation_status'])
        _audit('RECOMMEND_APPROVE', request, detail=f"Approved card '{card.titre}' (id={card_id})")

        return Response({'success': True, 'message': f'Carte "{card.titre}" promue en OFFICIAL'})


class ApproveItemView(APIView):
    """POST /api/admin/recommendations/item/<id>/approve/"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, item_id):
        try:
            item = ResourceItem.objects.select_related(
                'card', 'target_official_card'
            ).get(pk=item_id, recommended_to_community=True)
        except ResourceItem.DoesNotExist:
            return Response({'error': 'Item non trouvé'}, status=status.HTTP_404_NOT_FOUND)

        target_card = item.target_official_card
        if not target_card:
            target_card_id = request.data.get('target_card_id')
            if not target_card_id:
                return Response(
                    {'error': 'target_card_id requis (aucune carte cible définie)'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                target_card = ResourceCard.objects.get(pk=target_card_id, type='OFFICIAL')
            except ResourceCard.DoesNotExist:
                return Response(
                    {'error': 'Carte OFFICIAL cible non trouvée'},
                    status=status.HTTP_404_NOT_FOUND
                )

        ResourceItem.objects.create(
            card=target_card,
            type=item.type,
            label=item.label,
            url=item.url,
            file=item.file,
        )

        item.recommendation_status = 'APPROVED'
        item.save(update_fields=['recommendation_status'])
        _audit('RECOMMEND_APPROVE', request, detail=f"Approved item '{item.label}' (id={item_id}) → card '{target_card.titre}'")
        item.delete()

        return Response({
            'success': True,
            'message': f'Lien "{item.label}" ajouté à la carte "{target_card.titre}"'
        })


class RejectRecommendationView(APIView):
    """POST /api/admin/recommendations/reject/  body: {type, id}"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        rec_type = request.data.get('type')
        rec_id = request.data.get('id')

        if rec_type == 'card':
            try:
                card = ResourceCard.objects.get(pk=rec_id, recommended_to_community=True)
            except ResourceCard.DoesNotExist:
                return Response({'error': 'Carte non trouvée'}, status=status.HTTP_404_NOT_FOUND)
            card.recommendation_status = 'REJECTED'
            card.save(update_fields=['recommendation_status'])
            _audit('RECOMMEND_REJECT', request, detail=f"Rejected card '{card.titre}' (id={rec_id})")
            return Response({'success': True, 'message': f'Recommandation carte "{card.titre}" rejetée'})

        elif rec_type == 'item':
            try:
                item = ResourceItem.objects.get(pk=rec_id, recommended_to_community=True)
            except ResourceItem.DoesNotExist:
                return Response({'error': 'Item non trouvé'}, status=status.HTTP_404_NOT_FOUND)
            item.recommendation_status = 'REJECTED'
            item.save(update_fields=['recommendation_status'])
            _audit('RECOMMEND_REJECT', request, detail=f"Rejected item '{item.label}' (id={rec_id})")
            return Response({'success': True, 'message': f'Recommandation lien "{item.label}" rejetée'})

        return Response({'error': 'type doit être "card" ou "item"'}, status=status.HTTP_400_BAD_REQUEST)


class ListOfficialCardsView(APIView):
    """GET /api/admin/recommendations/official-cards/"""
    authentication_classes = [AdminJWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cards = ResourceCard.objects.filter(type='OFFICIAL').values('id', 'titre').order_by('titre')
        return Response({'cards': list(cards)})


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_ip(request) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')
