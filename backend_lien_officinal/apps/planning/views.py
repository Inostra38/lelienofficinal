from datetime import date, timedelta
import calendar

from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.team.models import Collaborator
from .calculator import pharmacy_week_summary
from .models import AbsenceRequest, OpeningHours, PharmacyDayStatus, PlanningSettings, Shift, TemplateShift, TimeAdjustment, WeekTemplate, WeekTemplateApplication
from .serializers import (
    AbsenceRequestCreateSerializer,
    AbsenceRequestSerializer,
    OpeningHoursSerializer,
    PharmacyDayStatusSerializer,
    PlanningSettingsSerializer,
    ShiftCreateSerializer,
    ShiftSerializer,
    ShiftUpdateSerializer,
    TemplateShiftSerializer,
    TimeAdjustmentCreateSerializer,
    TimeAdjustmentSerializer,
    WeekTemplateListSerializer,
    WeekTemplateSerializer,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_collaborator(request):
    """Lit le collaborateur actif depuis le claim JWT."""
    token = request.auth
    if not token or token.get('auth_type') != 'collaborator':
        return None
    collab_id = token.get('collaborator_id')
    if not collab_id:
        return None
    try:
        return Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
    except (Collaborator.DoesNotExist, ValueError):
        return None


def _parse_week(week_str) -> date:
    """
    Convertit '2025-W12' ou '2025-03-17' en date (lundi de la semaine).
    Retourne le lundi de la semaine courante si absent ou invalide.
    """
    if week_str:
        try:
            if 'W' in week_str:
                parts = week_str.split('-W')
                year, week = int(parts[0]), int(parts[1])
                return date.fromisocalendar(year, week, 1)
            else:
                d = date.fromisoformat(week_str)
                return d - timedelta(days=d.weekday())
        except (ValueError, IndexError):
            pass
    today = date.today()
    return today - timedelta(days=today.weekday())


# ── Vue semaine complète ─────────────────────────────────────────────────────

class WeekView(APIView):
    """
    GET /api/planning/week/?week=2025-W12
    Retourne shifts, statuts journaliers et résumé hebdomadaire.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        monday = _parse_week(request.query_params.get('week'))
        sunday = monday + timedelta(days=6)

        shifts = Shift.objects.filter(
            collaborator__pharmacy=request.user,
            start_datetime__date__gte=monday,
            start_datetime__date__lte=sunday,
        ).select_related('collaborator')

        day_statuses = PharmacyDayStatus.objects.filter(
            pharmacy=request.user,
            date__gte=monday,
            date__lte=sunday,
        )

        summary = pharmacy_week_summary(request.user, monday)

        tpl_app = WeekTemplateApplication.objects.filter(
            pharmacy=request.user, week_start=monday
        ).first()

        return Response({
            'week_start': monday.isoformat(),
            'week_end': sunday.isoformat(),
            'shifts': ShiftSerializer(shifts, many=True).data,
            'day_statuses': PharmacyDayStatusSerializer(day_statuses, many=True).data,
            'summary': summary,
            'template_letter': tpl_app.letter if tpl_app else None,
        })


# ── Shifts CRUD ──────────────────────────────────────────────────────────────

class ShiftListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ShiftCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            shift = serializer.save()
            return Response(ShiftSerializer(shift).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShiftDetailView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_shift(self, pk, pharmacy):
        try:
            return Shift.objects.get(pk=pk, collaborator__pharmacy=pharmacy)
        except Shift.DoesNotExist:
            return None

    def patch(self, request, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        shift = self._get_shift(pk, request.user)
        if not shift:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = ShiftUpdateSerializer(shift, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            shift.refresh_from_db()
            return Response(ShiftSerializer(shift).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        shift = self._get_shift(pk, request.user)
        if not shift:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        shift.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShiftPublishView(APIView):
    """POST /api/planning/shifts/{id}/publish/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        shift.is_published = True
        update_fields = ['is_published']
        if not shift.collaborator_snapshot and shift.collaborator:
            shift.collaborator_snapshot = f"{shift.collaborator.first_name} {shift.collaborator.last_name}"
            update_fields.append('collaborator_snapshot')
        shift.save(update_fields=update_fields)
        return Response(ShiftSerializer(shift).data)


class PublishWeekView(APIView):
    """POST /api/planning/publish-week/  { week: '2025-W12' }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        monday = _parse_week(request.data.get('week'))
        sunday = monday + timedelta(days=6)

        shifts_to_publish = Shift.objects.filter(
            collaborator__pharmacy=request.user,
            start_datetime__date__gte=monday,
            start_datetime__date__lte=sunday,
            is_published=False,
        ).select_related('collaborator')

        updated = 0
        for shift in shifts_to_publish:
            shift.is_published = True
            update_fields = ['is_published']
            if not shift.collaborator_snapshot and shift.collaborator:
                shift.collaborator_snapshot = f"{shift.collaborator.first_name} {shift.collaborator.last_name}"
                update_fields.append('collaborator_snapshot')
            shift.save(update_fields=update_fields)
            updated += 1

        return Response({'published': updated, 'week_start': monday.isoformat()})


class UnpublishWeekView(APIView):
    """POST /api/planning/unpublish-week/  { week: '2025-W12' }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        monday = _parse_week(request.data.get('week'))
        sunday = monday + timedelta(days=6)

        updated = Shift.objects.filter(
            collaborator__pharmacy=request.user,
            start_datetime__date__gte=monday,
            start_datetime__date__lte=sunday,
            is_published=True,
        ).update(is_published=False)

        return Response({'unpublished': updated, 'week_start': monday.isoformat()})


# ── Absences ─────────────────────────────────────────────────────────────────

class AbsenceListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = _get_collaborator(request)

        if actor and not actor.can_manage_planning:
            absences = AbsenceRequest.objects.filter(collaborator=actor)
        else:
            week_str = request.query_params.get('week')
            if week_str:
                monday = _parse_week(week_str)
                sunday = monday + timedelta(days=6)
                absences = AbsenceRequest.objects.filter(
                    collaborator__pharmacy=request.user,
                    start_date__lte=sunday,
                    end_date__gte=monday,
                ).select_related('collaborator', 'reviewed_by')
            else:
                absences = AbsenceRequest.objects.filter(
                    collaborator__pharmacy=request.user,
                ).select_related('collaborator', 'reviewed_by')

        return Response(AbsenceRequestSerializer(absences, many=True).data)

    def post(self, request):
        actor = _get_collaborator(request)
        if not actor:
            return Response({'detail': 'Session collaborateur requise.'}, status=status.HTTP_403_FORBIDDEN)

        is_manager = actor.can_manage_planning

        # Le manager peut poser une absence pour n'importe quel collaborateur
        if is_manager:
            collab_id = request.data.get('collaborator_id')
            if collab_id:
                try:
                    target = Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
                except (Collaborator.DoesNotExist, ValueError):
                    return Response({'detail': 'Collaborateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                target = actor
        else:
            target = actor

        # Découpages : on parse et valide les dates de base
        try:
            start_date = date.fromisoformat(request.data.get('start_date', ''))
            end_date   = date.fromisoformat(request.data.get('end_date', ''))
        except (ValueError, TypeError):
            return Response({'detail': 'Dates invalides.'}, status=status.HTTP_400_BAD_REQUEST)

        if start_date > end_date:
            return Response({'detail': 'La date de début doit être avant la date de fin.'}, status=status.HTTP_400_BAD_REQUEST)

        # Récupérer les jours bloqués (fermé ou garde de jour) sur la période
        nb_days      = (end_date - start_date).days + 1
        period_dates = [start_date + timedelta(days=i) for i in range(nb_days)]
        blocked_set  = set(
            PharmacyDayStatus.objects.filter(
                pharmacy=request.user,
                date__in=period_dates,
            ).filter(
                Q(status='closed') | Q(on_call_day=True)
            ).values_list('date', flat=True)
        )

        # Ajouter les jours déjà couverts par une absence existante du collaborateur
        existing_absences = AbsenceRequest.objects.filter(
            collaborator=target,
            status__in=[AbsenceRequest.Status.PENDING, AbsenceRequest.Status.APPROVED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        already_taken = set()
        for existing in existing_absences:
            cur = max(existing.start_date, start_date)
            end = min(existing.end_date, end_date)
            while cur <= end:
                already_taken.add(cur)
                cur += timedelta(days=1)
        blocked_set |= already_taken

        # Découper la plage en segments consécutifs en sautant les jours bloqués
        segments     = []
        seg_start    = None
        seg_end      = None
        for d in period_dates:
            if d not in blocked_set:
                if seg_start is None:
                    seg_start = d
                seg_end = d
            else:
                if seg_start is not None:
                    segments.append((seg_start, seg_end))
                    seg_start = seg_end = None
        if seg_start is not None:
            segments.append((seg_start, seg_end))

        skipped_days = len(blocked_set)

        if not segments:
            if already_taken and len(already_taken) == nb_days:
                return Response(
                    {'detail': 'Une absence existe déjà sur toute cette période.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {'detail': 'Tous les jours de la période sont fermés, en garde de jour ou déjà couverts par une absence.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Créer une absence par segment
        base_data = {k: v for k, v in request.data.items() if k not in ('start_date', 'end_date')}
        created_absences = []
        for seg_s, seg_e in segments:
            seg_data = {**base_data, 'start_date': seg_s.isoformat(), 'end_date': seg_e.isoformat()}
            serializer = AbsenceRequestCreateSerializer(
                data=seg_data,
                context={'collaborator': target, 'is_manager': is_manager, 'actor': actor},
            )
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            created_absences.append(serializer.save())

        return Response({
            'absences':     AbsenceRequestSerializer(created_absences, many=True).data,
            'skipped_days': skipped_days,
        }, status=status.HTTP_201_CREATED)


class AbsenceReviewView(APIView):
    """POST /api/planning/absences/{id}/approve/  ou  /reject/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, action):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            absence = AbsenceRequest.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except AbsenceRequest.DoesNotExist:
            return Response({'detail': 'Demande introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if action == 'approve':
            absence.status = AbsenceRequest.Status.APPROVED
        elif action == 'reject':
            absence.status = AbsenceRequest.Status.REJECTED
        else:
            return Response({'detail': 'Action invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        absence.reviewed_by = actor
        absence.reviewed_at = timezone.now()
        absence.save(update_fields=['status', 'reviewed_by', 'reviewed_at'])
        return Response(AbsenceRequestSerializer(absence).data)


# ── PharmacyDayStatus ─────────────────────────────────────────────────────────

class DayStatusListCreateView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        week_str = request.query_params.get('week')
        if week_str:
            monday = _parse_week(week_str)
            sunday = monday + timedelta(days=6)
            qs = PharmacyDayStatus.objects.filter(
                pharmacy=request.user, date__gte=monday, date__lte=sunday
            )
        else:
            qs = PharmacyDayStatus.objects.filter(pharmacy=request.user)
        return Response(PharmacyDayStatusSerializer(qs, many=True).data)

    def post(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = PharmacyDayStatusSerializer(data=request.data)
        if serializer.is_valid():
            defaults = {
                'status': serializer.validated_data.get('status', PharmacyDayStatus.Status.OPEN),
                'note':   serializer.validated_data.get('note', ''),
            }
            if 'on_call_day' in serializer.validated_data:
                defaults['on_call_day'] = serializer.validated_data['on_call_day']
            if 'on_call_night' in serializer.validated_data:
                defaults['on_call_night'] = serializer.validated_data['on_call_night']
            day_status_obj, _ = PharmacyDayStatus.objects.update_or_create(
                pharmacy=request.user,
                date=serializer.validated_data['date'],
                defaults=defaults,
            )
            return Response(PharmacyDayStatusSerializer(day_status_obj).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── DayStatus DELETE ─────────────────────────────────────────────────────────

class DayStatusDeleteView(APIView):
    """DELETE /api/planning/day-status/{date}/  — supprime le statut d'un jour"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, iso_date):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        deleted, _ = PharmacyDayStatus.objects.filter(
            pharmacy=request.user,
            date=iso_date,
        ).delete()

        if not deleted:
            return Response({'detail': 'Statut introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Résumé mensuel absences ───────────────────────────────────────────────────

class MonthlyAbsenceSummaryView(APIView):
    """
    GET /api/planning/absences/monthly-summary/?month=2025-03
    Retourne par jour du mois la liste des absences approuvées (initiales + type).
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        month_str = request.query_params.get('month')
        try:
            year, mo = int(month_str.split('-')[0]), int(month_str.split('-')[1])
        except (AttributeError, IndexError, ValueError):
            today = date.today()
            year, mo = today.year, today.month

        first_day = date(year, mo, 1)
        last_day  = date(year, mo, calendar.monthrange(year, mo)[1])

        absences = AbsenceRequest.objects.filter(
            collaborator__pharmacy=request.user,
            collaborator__is_active=True,
            status=AbsenceRequest.Status.APPROVED,
            start_date__lte=last_day,
            end_date__gte=first_day,
        ).select_related('collaborator')

        # Construit un dict date → liste d'entrées
        result: dict[str, list] = {}
        for absence in absences:
            current = max(absence.start_date, first_day)
            end     = min(absence.end_date,   last_day)
            while current <= end:
                iso = current.isoformat()
                result.setdefault(iso, []).append({
                    'collaborator_id': absence.collaborator.id,
                    'initials': f"{absence.collaborator.first_name[0]}{absence.collaborator.last_name[0]}".upper(),
                    'color':    absence.collaborator.color,
                    'type':     absence.type,
                })
                current += timedelta(days=1)

        return Response(result)


# ── PlanningSettings ──────────────────────────────────────────────────────────

class PlanningSettingsView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_or_create_settings(self, pharmacy):
        obj, _ = PlanningSettings.objects.get_or_create(pharmacy=pharmacy)
        return obj

    def get(self, request):
        return Response(PlanningSettingsSerializer(self._get_or_create_settings(request.user)).data)

    def patch(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        settings_obj = self._get_or_create_settings(request.user)
        serializer = PlanningSettingsSerializer(settings_obj, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── WeekTemplate ──────────────────────────────────────────────────────────────

class WeekTemplateListView(APIView):
    """GET /api/planning/templates/  → liste des templates de la pharmacie"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        templates = WeekTemplate.objects.filter(pharmacy=request.user).prefetch_related('shifts')
        return Response(WeekTemplateListSerializer(templates, many=True).data)


class WeekTemplateDetailView(APIView):
    """
    GET   /api/planning/templates/{letter}/  → détail + shifts
    PATCH /api/planning/templates/{letter}/  → modifier apply_from
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_or_create(self, pharmacy, letter):
        if letter not in [c[0] for c in WeekTemplate.Letter.choices]:
            return None
        template, _ = WeekTemplate.objects.get_or_create(pharmacy=pharmacy, letter=letter)
        return template

    def get(self, request, letter):
        template = self._get_or_create(request.user, letter.upper())
        if not template:
            return Response({'detail': 'Lettre invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(WeekTemplateSerializer(template).data)

    def patch(self, request, letter):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        template = self._get_or_create(request.user, letter.upper())
        if not template:
            return Response({'detail': 'Lettre invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = WeekTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TemplateShiftListCreateView(APIView):
    """
    GET  /api/planning/templates/{letter}/shifts/  → shifts du template
    POST /api/planning/templates/{letter}/shifts/  → ajouter un shift
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_template(self, pharmacy, letter):
        try:
            return WeekTemplate.objects.get(pharmacy=pharmacy, letter=letter.upper())
        except WeekTemplate.DoesNotExist:
            return None

    def get(self, request, letter):
        template = self._get_template(request.user, letter)
        if not template:
            return Response({'detail': 'Template introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(TemplateShiftSerializer(template.shifts.all(), many=True).data)

    def post(self, request, letter):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        template, _ = WeekTemplate.objects.get_or_create(
            pharmacy=request.user, letter=letter.upper()
        )

        collab_id = request.data.get('collaborator_id')
        try:
            collaborator = Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
        except (Collaborator.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'Collaborateur introuvable.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TemplateShiftSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(template=template, collaborator=collaborator)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TemplateShiftDetailView(APIView):
    """
    PATCH  /api/planning/templates/{letter}/shifts/{id}/
    DELETE /api/planning/templates/{letter}/shifts/{id}/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def _get_shift(self, pk, pharmacy, letter):
        try:
            return TemplateShift.objects.get(
                pk=pk, template__pharmacy=pharmacy, template__letter=letter.upper()
            )
        except TemplateShift.DoesNotExist:
            return None

    def patch(self, request, letter, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        shift = self._get_shift(pk, request.user, letter)
        if not shift:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = TemplateShiftSerializer(shift, data=request.data, partial=True)
        if serializer.is_valid():
            # Si collaborator_id fourni, mettre à jour le collaborateur
            collab_id = request.data.get('collaborator_id')
            if collab_id:
                try:
                    shift.collaborator = Collaborator.objects.get(
                        id=int(collab_id), pharmacy=request.user, is_active=True
                    )
                except (Collaborator.DoesNotExist, ValueError):
                    return Response({'detail': 'Collaborateur introuvable.'}, status=status.HTTP_400_BAD_REQUEST)
            serializer.save()
            shift.refresh_from_db()
            return Response(TemplateShiftSerializer(shift).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, letter, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        shift = self._get_shift(pk, request.user, letter)
        if not shift:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        shift.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TemplateApplyView(APIView):
    """POST /api/planning/templates/{letter}/apply/  { week: '2025-W12' }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, letter):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            template = WeekTemplate.objects.get(pharmacy=request.user, letter=letter.upper())
        except WeekTemplate.DoesNotExist:
            return Response({'detail': 'Template introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        monday = _parse_week(request.data.get('week'))
        force   = bool(request.data.get('force', False))
        created = skipped = replaced = absence_protected = day_protected = 0

        from datetime import datetime as dt
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Paris')

        # Pré-charger les statuts de la semaine pour éviter N requêtes
        week_dates = [monday + timedelta(days=i) for i in range(7)]
        day_statuses = {
            s.date: s
            for s in PharmacyDayStatus.objects.filter(
                pharmacy=request.user,
                date__in=week_dates,
            )
        }

        for tshift in template.shifts.select_related('collaborator'):
            target_date = monday + timedelta(days=tshift.day_of_week)

            # Jour fermé ou en garde de jour → template non appliqué
            # (garde de nuit seule n'affecte pas les shifts de la journée)
            ds = day_statuses.get(target_date)
            if ds:
                if ds.status == 'closed' or ds.on_call_day:
                    day_protected += 1
                    continue

            # Absence approuvée ou en attente → protégé, même en mode force
            has_absence = AbsenceRequest.objects.filter(
                collaborator=tshift.collaborator,
                start_date__lte=target_date,
                end_date__gte=target_date,
                status__in=[AbsenceRequest.Status.APPROVED, AbsenceRequest.Status.PENDING],
            ).exists()
            if has_absence:
                absence_protected += 1
                continue

            existing_qs = Shift.objects.filter(
                collaborator=tshift.collaborator,
                start_datetime__date=target_date,
            )
            if existing_qs.exists():
                if not force:
                    skipped += 1
                    continue
                existing_qs.delete()
                replaced += 1

            start_dt = timezone.make_aware(dt.combine(target_date, tshift.start_time), tz)
            end_dt   = timezone.make_aware(dt.combine(target_date, tshift.end_time), tz)

            Shift(
                collaborator=tshift.collaborator,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_published=False,
                note=tshift.note or '',
            ).save(bypass_validation=True)
            created += 1

        WeekTemplateApplication.objects.update_or_create(
            pharmacy=request.user,
            week_start=monday,
            defaults={'letter': letter.upper()},
        )

        return Response({'created': created, 'skipped': skipped, 'replaced': replaced, 'absence_protected': absence_protected, 'day_protected': day_protected, 'week_start': monday.isoformat()})


# ── OpeningHours ───────────────────────────────────────────────────────────────

class OpeningHoursView(APIView):
    """
    GET  /api/planning/opening-hours/           → liste des créneaux de la pharmacie
    POST /api/planning/opening-hours/           → créer un créneau
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = OpeningHours.objects.filter(pharmacy=request.user)
        return Response(OpeningHoursSerializer(qs, many=True).data)

    def post(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = OpeningHoursSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(pharmacy=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class OpeningHoursDetailView(APIView):
    """DELETE /api/planning/opening-hours/{pk}/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            slot = OpeningHours.objects.get(pk=pk, pharmacy=request.user)
        except OpeningHours.DoesNotExist:
            return Response({'detail': 'Introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        slot.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── TimeAdjustment ────────────────────────────────────────────────────────────

class TimeAdjustmentListCreateView(APIView):
    """
    GET  /api/planning/adjustments/?week=2025-W12
    POST /api/planning/adjustments/
    """
    authentication_classes = [JWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def get(self, request):
        actor    = _get_collaborator(request)
        week_str = request.query_params.get('week')
        monday   = _parse_week(week_str)
        sunday   = monday + timedelta(days=6)

        if actor and not actor.can_manage_planning:
            qs = TimeAdjustment.objects.filter(
                collaborator=actor,
                date__gte=monday, date__lte=sunday,
            ).select_related('collaborator', 'declared_by')
        else:
            qs = TimeAdjustment.objects.filter(
                collaborator__pharmacy=request.user,
                date__gte=monday, date__lte=sunday,
            ).select_related('collaborator', 'declared_by')

        return Response(TimeAdjustmentSerializer(qs, many=True).data)

    def post(self, request):
        actor = _get_collaborator(request)
        if not actor:
            return Response({'detail': 'Session collaborateur requise.'}, status=status.HTTP_403_FORBIDDEN)

        is_manager = actor.can_manage_planning

        if is_manager:
            collab_id = request.data.get('collaborator_id')
            if collab_id:
                try:
                    target = Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
                except (Collaborator.DoesNotExist, ValueError):
                    return Response({'detail': 'Collaborateur introuvable.'}, status=status.HTTP_404_NOT_FOUND)
            else:
                target = actor
        else:
            target = actor

        serializer = TimeAdjustmentCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        adj = serializer.save(collaborator=target, declared_by=actor)
        return Response(TimeAdjustmentSerializer(adj).data, status=status.HTTP_201_CREATED)


class TimeAdjustmentDeleteView(APIView):
    """DELETE /api/planning/adjustments/{pk}/"""
    authentication_classes = [JWTAuthentication]
    permission_classes     = [IsAuthenticated]

    def delete(self, request, pk):
        actor = _get_collaborator(request)
        try:
            adj = TimeAdjustment.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except TimeAdjustment.DoesNotExist:
            return Response({'detail': 'Introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        # Staff peut supprimer ses propres ajustements, manager peut tout supprimer
        if actor and not actor.can_manage_planning and adj.collaborator != actor:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        adj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Analytics ─────────────────────────────────────────────────────────────────

class AnalyticsView(APIView):
    """
    GET /api/planning/analytics/?period=week|month|year&date=YYYY-MM-DD
    Retourne les données analytiques du planning pour la période demandée.
    Accessible uniquement aux managers planning.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        period   = request.query_params.get('period', 'month')
        date_str = request.query_params.get('date', date.today().isoformat())
        try:
            ref_date = date.fromisoformat(date_str)
        except ValueError:
            ref_date = date.today()

        if period == 'week':
            date_from = ref_date - timedelta(days=ref_date.weekday())
            date_to   = date_from + timedelta(days=6)
        elif period == 'year':
            date_from = ref_date.replace(month=1, day=1)
            date_to   = ref_date.replace(month=12, day=31)
        else:  # month (default)
            date_from = ref_date.replace(day=1)
            date_to   = ref_date.replace(day=calendar.monthrange(ref_date.year, ref_date.month)[1])

        from .analytics import PlanningAnalytics
        analytics = PlanningAnalytics(request.user)

        data = {
            'period':        period,
            'date_from':     date_from.isoformat(),
            'date_to':       date_to.isoformat(),
            'hours_summary': analytics.hours_summary(date_from, date_to),
            'absences':      analytics.absences_summary(date_from, date_to),
            'cp_balance':    analytics.cp_balance(date_from, date_to),
            'coverage':      analytics.coverage_rate(date_from, date_to),
            'on_call':       analytics.on_call_summary(date_from, date_to),
        }
        if period == 'year':
            data['monthly_evolution'] = analytics.monthly_evolution(ref_date.year)

        return Response(data)
