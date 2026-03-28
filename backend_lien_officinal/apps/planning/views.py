from datetime import date, timedelta
import calendar
import json

import anthropic as anthropic_sdk
from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.team.models import Collaborator, ContractHistory
from apps.core.auth_helpers import get_collaborator_from_jwt as _get_collaborator
from .calculator import pharmacy_week_summary
from .utils import get_jours_feries
from .models import AbsenceRequest, Constraint, ConstraintSet, OpeningHours, PharmacyDayStatus, PlanningSettings, Shift, TemplateShift, TimeAdjustment, WeekTemplate, WeekTemplateApplication
from .serializers import (
    AbsenceRequestCreateSerializer,
    ConstraintSerializer,
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
            date__gte=monday - timedelta(days=1),  # inclut le dimanche précédent (garde de nuit → lundi matin)
            date__lte=sunday,
        )

        summary = pharmacy_week_summary(request.user, monday)

        tpl_app = WeekTemplateApplication.objects.filter(
            pharmacy=request.user, week_start=monday
        ).first()

        # Contrat le plus récent par collaborateur (pour filtrage front-end jour par jour)
        from django.db.models import Max
        latest_starts = (
            ContractHistory.objects
            .filter(collaborator__pharmacy=request.user)
            .values('collaborator_id')
            .annotate(latest=Max('start_date'))
        )
        latest_map = {row['collaborator_id']: row['latest'] for row in latest_starts}

        contracts_by_collab = {}
        for c in ContractHistory.objects.filter(
            collaborator__pharmacy=request.user,
        ).values('collaborator_id', 'start_date', 'end_date'):
            cid = c['collaborator_id']
            if latest_map.get(cid) == c['start_date']:
                contracts_by_collab[cid] = {
                    'start_date': c['start_date'].isoformat(),
                    'end_date': c['end_date'].isoformat() if c['end_date'] else None,
                }

        ps = PlanningSettings.objects.filter(pharmacy=request.user).first()

        def _fmt_time(t):
            return str(t)[:5] if t else None

        return Response({
            'week_start': monday.isoformat(),
            'week_end': sunday.isoformat(),
            'shifts': ShiftSerializer(shifts, many=True).data,
            'day_statuses': PharmacyDayStatusSerializer(day_statuses, many=True).data,
            'summary': summary,
            'template_letter': tpl_app.letter if tpl_app else None,
            'contracts': contracts_by_collab,
            'on_call_sunday':      ps.on_call_sunday      if ps else False,
            'on_call_day_start':   _fmt_time(ps.on_call_day_start)   if ps else None,
            'on_call_day_end':     _fmt_time(ps.on_call_day_end)     if ps else None,
            'on_call_night_start': _fmt_time(ps.on_call_night_start) if ps else None,
            'on_call_night_end':   _fmt_time(ps.on_call_night_end)   if ps else None,
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

        # Ajouter les dimanches et jours fériés (non travaillés par défaut)
        years_in_period = {d.year for d in period_dates}
        feries = set()
        for y in years_in_period:
            feries.update(get_jours_feries(y))
        for d in period_dates:
            if d.weekday() == 6 or d in feries:  # dimanche ou férié
                blocked_set.add(d)

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
        absence_type = request.data.get('type', 'injustifiee')
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
            absence = serializer.save()

            # Pour les CP : calcul des jours ouvrés réels (lun–sam, hors fériés)
            if absence_type == 'cp':
                n_days = (seg_e - seg_s).days + 1
                seg_dates = [seg_s + timedelta(days=i) for i in range(n_days)]
                seg_years = {d.year for d in seg_dates}
                seg_feries = set()
                for y in seg_years:
                    seg_feries.update(get_jours_feries(y))
                working_days = sum(
                    1 for d in seg_dates
                    if d.weekday() < 6 and d not in seg_feries
                )
                AbsenceRequest.objects.filter(pk=absence.pk).update(working_days_count=working_days)
                absence.working_days_count = working_days

            created_absences.append(absence)

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


class TemplateBulkReplaceView(APIView):
    """
    POST /api/planning/templates/{letter}/bulk-replace/
    Body : [{"collaborator_id": 1, "day_of_week": 0, "start_time": "08:00", "end_time": "16:00", "note": ""}, ...]
    Supprime tous les TemplateShifts existants pour cette lettre, recrée en transaction atomique.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, letter):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        items = request.data
        if not isinstance(items, list):
            return Response({'detail': 'Liste de shifts attendue.'}, status=status.HTTP_400_BAD_REQUEST)

        letter_upper = letter.upper()

        with transaction.atomic():
            template, _ = WeekTemplate.objects.get_or_create(
                pharmacy=request.user, letter=letter_upper
            )
            template.shifts.all().delete()

            created = []
            for item in items:
                collab_id = item.get('collaborator_id')
                try:
                    collaborator = Collaborator.objects.get(id=int(collab_id), pharmacy=request.user, is_active=True)
                except (Collaborator.DoesNotExist, ValueError, TypeError):
                    return Response(
                        {'detail': f'Collaborateur {collab_id} introuvable.'},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                serializer = TemplateShiftSerializer(data=item)
                if not serializer.is_valid():
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                shift = serializer.save(template=template, collaborator=collaborator)
                created.append(shift)

        return Response(TemplateShiftSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


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
        created = skipped = replaced = absence_protected = day_protected = ferie_skipped = 0
        violations = []
        ferie_days = []

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

        # Jours fériés des années concernées (dict date → label)
        from .utils import get_label_ferie
        feries_map = {}
        for y in {d.year for d in week_dates}:
            for ferie_date in get_jours_feries(y):
                feries_map[ferie_date] = get_label_ferie(ferie_date, y)

        for tshift in template.shifts.select_related('collaborator'):
            target_date = monday + timedelta(days=tshift.day_of_week)

            # Jour férié → skip
            if target_date in feries_map:
                ferie_skipped += 1
                iso = target_date.isoformat()
                if not any(f['date'] == iso for f in ferie_days):
                    ferie_days.append({'date': iso, 'reason': f"Jour férié — {feries_map[target_date]}"})
                continue

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

            shift = Shift(
                collaborator=tshift.collaborator,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_published=False,
                note=tshift.note or '',
            )
            try:
                shift.save()
                created += 1
            except ValidationError as e:
                collab_name = f"{tshift.collaborator.first_name} {tshift.collaborator.last_name}"
                violations.append({
                    'shift_date': str(target_date),
                    'collaborator': collab_name,
                    'error': e.messages[0] if e.messages else str(e),
                })

        WeekTemplateApplication.objects.update_or_create(
            pharmacy=request.user,
            week_start=monday,
            defaults={'letter': letter.upper()},
        )

        return Response({'created': created, 'skipped': skipped, 'replaced': replaced, 'absence_protected': absence_protected, 'day_protected': day_protected, 'ferie_skipped': ferie_skipped, 'ferie_days': ferie_days, 'week_start': monday.isoformat(), 'violations': violations})


# ── OpeningHours ───────────────────────────────────────────────────────────────

class BulkShiftUpdateView(APIView):
    """
    POST /api/planning/templates/<letter>/apply-bulk/
    Body : [{"date": "2026-03-19", "collaborator_id": 12, "start": "08:00", "end": "16:00", "post": "comptoir"}, ...]
    Supprime tous les shifts existants sur les dates reçues, recrée en transaction atomique.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, letter):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        items = request.data
        if not isinstance(items, list) or not items:
            return Response({'detail': 'Liste de shifts attendue.'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime as dt
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Paris')

        # Collecter toutes les dates couvertes
        try:
            dates = list({date.fromisoformat(item['date']) for item in items})
        except (KeyError, ValueError) as e:
            return Response({'detail': f'Format de date invalide : {e}'}, status=status.HTTP_400_BAD_REQUEST)

        # Supprimer tous les shifts existants sur ces dates pour cette pharmacie
        Shift.objects.filter(
            collaborator__pharmacy=request.user,
            start_datetime__date__in=dates,
        ).delete()

        created_shifts = []
        violations = []
        for item in items:
            try:
                collab_id  = item['collaborator_id']
                shift_date = date.fromisoformat(item['date'])
                start_time = dt.strptime(item['start'], '%H:%M').time()
                end_time   = dt.strptime(item['end'], '%H:%M').time()
            except (KeyError, ValueError) as e:
                return Response(
                    {'detail': f'Données invalides dans le shift : {e}'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                collaborator = Collaborator.objects.get(id=collab_id, pharmacy=request.user)
            except Collaborator.DoesNotExist:
                return Response(
                    {'detail': f'Collaborateur {collab_id} introuvable ou non autorisé.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            start_dt = timezone.make_aware(dt.combine(shift_date, start_time), tz)
            end_dt   = timezone.make_aware(dt.combine(shift_date, end_time), tz)

            shift = Shift(
                collaborator=collaborator,
                start_datetime=start_dt,
                end_datetime=end_dt,
                is_published=False,
                note=item.get('post', '') or item.get('note', ''),
            )
            try:
                shift.save()
                created_shifts.append(shift)
            except ValidationError as e:
                collab_name = f"{collaborator.first_name} {collaborator.last_name}"
                violations.append({
                    'shift_date': str(shift_date),
                    'collaborator': collab_name,
                    'error': e.messages[0] if e.messages else str(e),
                })

        return Response({'shifts': ShiftSerializer(created_shifts, many=True).data, 'violations': violations})


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


# ── Contraintes planning ───────────────────────────────────────────────────────

REGULATORY_DEFAULTS = [
    "Repos quotidien minimum de 11 heures entre deux shifts",
    "Amplitude journalière maximale de 12 heures",
    "Durée de travail effectif maximale de 10 heures par jour",
    "Repos hebdomadaire de 35 heures consécutives minimum",
    "Maximum 48 heures de travail par semaine",
    "Maximum 44 heures de travail en moyenne sur 12 semaines",
    "Majoration de 20% pour les heures entre 20h-22h et 5h-8h",
    "Majoration de 40% pour les heures entre 22h et 5h",
    "Heures supplémentaires : majoration 25% pour les 8 premières heures, 50% au-delà",
]


def _get_or_create_constraint_set(pharmacy):
    """Get or create a ConstraintSet for the pharmacy, creating defaults if new."""
    constraint_set, created = ConstraintSet.objects.get_or_create(pharmacy=pharmacy)
    if created:
        for idx, desc in enumerate(REGULATORY_DEFAULTS):
            Constraint.objects.create(
                constraint_set=constraint_set,
                level=Constraint.Level.REGULATORY,
                description=desc,
                order=idx,
                is_active=True,
            )
    return constraint_set


class ConstraintsView(APIView):
    """
    GET  /api/planning/constraints/   → list all constraints for the pharmacy
    POST /api/planning/constraints/   → add a new constraint (pharmacy or personal)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        constraint_set = _get_or_create_constraint_set(request.user)
        constraints = constraint_set.constraints.all()
        return Response(ConstraintSerializer(constraints, many=True).data)

    def post(self, request):
        constraint_set = _get_or_create_constraint_set(request.user)
        level = request.data.get('level', 'pharmacy')
        if level == 'regulatory':
            return Response(
                {"detail": "Impossible de créer une contrainte réglementaire."},
                status=status.HTTP_403_FORBIDDEN
            )
        collaborator_id = request.data.get('collaborator_id')
        collaborator = None
        if collaborator_id:
            try:
                collaborator = Collaborator.objects.get(
                    id=collaborator_id, pharmacy=request.user
                )
            except Collaborator.DoesNotExist:
                return Response({"detail": "Collaborateur introuvable."}, status=status.HTTP_404_NOT_FOUND)
        constraint = Constraint.objects.create(
            constraint_set=constraint_set,
            level=level,
            collaborator=collaborator,
            description=request.data.get('description', ''),
            is_active=True,
            order=request.data.get('order', 0),
        )
        return Response(ConstraintSerializer(constraint).data, status=status.HTTP_201_CREATED)


class ConstraintDetailView(APIView):
    """
    PATCH  /api/planning/constraints/{id}/  → update description / toggle active
    DELETE /api/planning/constraints/{id}/  → delete (forbidden for regulatory)
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def _get_constraint(self, request, pk):
        try:
            return Constraint.objects.get(
                id=pk, constraint_set__pharmacy=request.user
            )
        except Constraint.DoesNotExist:
            return None

    def patch(self, request, pk):
        constraint = self._get_constraint(request, pk)
        if not constraint:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if 'description' in request.data:
            constraint.description = request.data['description']
        if 'is_active' in request.data:
            constraint.is_active = request.data['is_active']
        if 'order' in request.data:
            constraint.order = request.data['order']
        constraint.save()
        return Response(ConstraintSerializer(constraint).data)

    def delete(self, request, pk):
        constraint = self._get_constraint(request, pk)
        if not constraint:
            return Response({"detail": "Introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if constraint.level == Constraint.Level.REGULATORY:
            return Response(
                {"detail": "Les contraintes réglementaires ne peuvent pas être supprimées."},
                status=status.HTTP_403_FORBIDDEN
            )
        constraint.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GenerateTemplateView(APIView):
    """POST /api/planning/constraints/generate/"""
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request):
        from django_ratelimit.core import is_ratelimited
        limited = is_ratelimited(
            request,
            fn=GenerateTemplateView.post,
            key='user',
            rate='10/h',
            method='POST',
            increment=True,
        )
        if limited:
            return Response(
                {'detail': 'Limite atteinte : 10 générations IA par heure. Réessayez plus tard.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        rotation     = int(request.data.get('rotation', 2))
        conversation = request.data.get('conversation', [])

        constraint_set = _get_or_create_constraint_set(request.user)
        constraints    = constraint_set.constraints.filter(is_active=True)

        regulatory = [c.description for c in constraints if c.level == 'regulatory']
        pharmacy_c = [c.description for c in constraints if c.level == 'pharmacy']
        personal_c = []
        for c in constraints.filter(level='personal'):
            name = f"{c.collaborator.first_name} {c.collaborator.last_name}" if c.collaborator else ""
            personal_c.append(f"{name} : {c.description}" if name else c.description)

        collaborators = [
            {
                "id":    c.id,
                "name":  f"{c.first_name} {c.last_name}",
                "role":  c.get_role_display(),
                "hours": float(c.weekly_hours),
            }
            for c in Collaborator.objects.filter(pharmacy=request.user, is_active=True)
        ]

        # Opening hours grouped by day
        opening_slots = OpeningHours.objects.filter(pharmacy=request.user).order_by('day_of_week', 'start_time')
        day_names = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
        opening: dict = {}
        for slot in opening_slots:
            day = day_names[slot.day_of_week]
            if day not in opening:
                opening[day] = []
            opening[day].append(f"{slot.start_time.strftime('%H:%M')}-{slot.end_time.strftime('%H:%M')}")

        letters = ['A', 'B', 'C', 'D'][:rotation]
        rotation_label = '/'.join(letters)

        system_prompt = f"""Tu es un assistant expert en planning de pharmacie d'officine française.
Tu connais parfaitement la Convention Collective Nationale de la Pharmacie.

Tu dois générer un planning template sur une rotation de {rotation} semaine(s) ({rotation_label}).

COLLABORATEURS :
{json.dumps(collaborators, ensure_ascii=False, indent=2)}

HORAIRES D'OUVERTURE :
{json.dumps(opening, ensure_ascii=False, indent=2)}

CONTRAINTES PAR ORDRE DE PRIORITÉ :

[NIVEAU 1 - RÉGLEMENTAIRE - Non négociable] :
{chr(10).join(f"- {r}" for r in regulatory)}

[NIVEAU 2 - PHARMACIE - Respecter sauf conflit niveau 1] :
{chr(10).join(f"- {p}" for p in pharmacy_c) if pharmacy_c else "- Aucune contrainte pharmacie définie"}

[NIVEAU 3 - PERSONNELLE - Best effort, cédées en dernier recours] :
{chr(10).join(f"- {p}" for p in personal_c) if personal_c else "- Aucune contrainte personnelle définie"}

RÈGLES DE GÉNÉRATION :
- Chaque collaborateur doit respecter son volume horaire hebdomadaire contractuel
- Les shifts doivent être dans les horaires d'ouverture
- day_of_week : 0=Lundi, 1=Mardi, 2=Mercredi, 3=Jeudi, 4=Vendredi, 5=Samedi, 6=Dimanche
- Un jour absent dans opening = pharmacie fermée ce jour
- Indiquer les violations si certaines contraintes ne peuvent pas être respectées simultanément

FORMAT DE RÉPONSE OBLIGATOIRE :
Réponds avec deux blocs distincts :

1. Un paragraphe court expliquant les choix effectués et les éventuels compromis.

2. Un bloc JSON valide avec exactement cette structure :
```json
{{
  "weeks": {{
    "A": [
      {{
        "collaborator_id": 1,
        "day_of_week": 0,
        "start_time": "08:30",
        "end_time": "13:00",
        "note": ""
      }}
    ]
  }},
  "violations": [
    {{
      "level": "personal",
      "description": "La contrainte X n'a pas pu être respectée car..."
    }}
  ]
}}
```
Inclure uniquement les semaines {rotation_label}.
"""

        messages = [{"role": m["role"], "content": m["content"]} for m in conversation]
        if not messages:
            messages.append({
                "role": "user",
                "content": "Génère un template de planning optimisé en respectant toutes les contraintes."
            })

        api_key = getattr(django_settings, 'ANTHROPIC_API_KEY', None)
        if not api_key:
            return Response(
                {"detail": "ANTHROPIC_API_KEY non configurée."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        client = anthropic_sdk.Anthropic(api_key=api_key)
        ai_response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=8000,
            system=system_prompt,
            messages=messages,
        )

        assistant_message = ai_response.content[0].text

        from .utils import parse_ai_planning_response, AIParseError
        try:
            template_json = parse_ai_planning_response(assistant_message)
        except AIParseError as exc:
            import logging
            logging.getLogger(__name__).error("AI parse error: %s\nRaw response: %s", exc, assistant_message)
            return Response(
                {"detail": f"La réponse de l'IA n'a pas pu être interprétée : {exc}"},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            "message":      assistant_message,
            "template":     template_json,
            "conversation": conversation + [
                {"role": "assistant", "content": assistant_message}
            ]
        })


class PayeAnalyticsView(APIView):
    """
    GET /api/planning/analytics/paie/?month=2026-03
    Retourne le récap paie CCN pour le mois demandé.
    Managers uniquement.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actor = _get_collaborator(request)
        if actor and not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        month_str = request.query_params.get('month', '')
        if not month_str or len(month_str) < 7:
            return Response({'error': 'Paramètre month requis (YYYY-MM).'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            year = int(month_str[:4])
            month = int(month_str[5:7])
        except ValueError:
            return Response({'error': 'Format month invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        from .paye_analytics import compute_paye_summary
        data = compute_paye_summary(request.user, year, month)
        return Response(data)


# ── Drawer shift — actions ─────────────────────────────────────────────────────

class SplitShiftView(APIView):
    """POST /api/planning/shifts/<pk>/split/  { split_time: "HH:MM" }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if not actor or not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        split_time_str = request.data.get('split_time', '')
        try:
            from datetime import time as dt_time
            h, m = map(int, split_time_str.split(':'))
            split_time_obj = dt_time(h, m)
        except (ValueError, AttributeError):
            return Response({'detail': 'split_time requis au format HH:MM.'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime as dt_cls
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Paris')

        orig_start = shift.start_datetime.astimezone(tz)
        orig_end   = shift.end_datetime.astimezone(tz)

        split_dt = timezone.make_aware(dt_cls.combine(orig_start.date(), split_time_obj), tz)
        # Si l'heure de coupure est avant le début (cross-midnight), on essaie le lendemain
        if split_dt <= orig_start:
            split_dt = timezone.make_aware(
                dt_cls.combine(orig_start.date() + timedelta(days=1), split_time_obj), tz
            )

        if split_dt >= orig_end:
            return Response(
                {'detail': 'L\'heure de coupure doit être comprise entre le début et la fin du shift.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        dur_1_h = (split_dt - orig_start).total_seconds() / 3600
        dur_2_h = (orig_end - split_dt).total_seconds() / 3600
        if dur_1_h > 12 or dur_2_h > 12:
            return Response(
                {'detail': 'Un des deux shifts résultants dépasse l\'amplitude maximale de 12h.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        common = dict(
            collaborator=shift.collaborator,
            collaborator_snapshot=shift.collaborator_snapshot,
            is_published=shift.is_published,
            is_extra_hour=shift.is_extra_hour,
            note=shift.note,
        )
        with transaction.atomic():
            shift.delete()
            s1 = Shift.objects.create(start_datetime=orig_start, end_datetime=split_dt, **common)
            s2 = Shift.objects.create(start_datetime=split_dt, end_datetime=orig_end, **common)

        return Response({'shift_1': ShiftSerializer(s1).data, 'shift_2': ShiftSerializer(s2).data},
                        status=status.HTTP_201_CREATED)


class TransformShiftView(APIView):
    """POST /api/planning/shifts/<pk>/transform/  { transform_type: "cp"|... }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    _VALID = {'cp', 'injustifiee', 'conge_exceptionnel', 'maladie', 'rcr', 'sans_solde', 'formation'}

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if not actor or not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        t = request.data.get('transform_type', '')
        if t not in self._VALID:
            return Response({'detail': f'transform_type invalide. Valeurs acceptées : {", ".join(sorted(self._VALID))}.'}, status=status.HTTP_400_BAD_REQUEST)

        shift.is_absent = True
        shift.absence_type = t
        shift.save(update_fields=['is_absent', 'absence_type'])

        if t == 'cp' and shift.collaborator:
            shift_date = shift.start_datetime.astimezone(__import__('zoneinfo').ZoneInfo('Europe/Paris')).date()
            AbsenceRequest.objects.get_or_create(
                collaborator=shift.collaborator,
                start_date=shift_date,
                end_date=shift_date,
                type=AbsenceRequest.AbsenceType.CP,
                defaults={'status': AbsenceRequest.Status.APPROVED, 'posted_by_manager': True},
            )

        shift.refresh_from_db()
        return Response(ShiftSerializer(shift).data)


class EarlyDepartureView(APIView):
    """POST /api/planning/shifts/<pk>/early-departure/  { actual_end_time, note }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if not actor or not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        actual_end_str = request.data.get('actual_end_time', '')
        note = request.data.get('note', '')
        try:
            h, m = map(int, actual_end_str.split(':'))
        except (ValueError, AttributeError):
            return Response({'detail': 'actual_end_time requis au format HH:MM.'}, status=status.HTTP_400_BAD_REQUEST)

        from datetime import datetime as dt_cls, time as dt_time
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Paris')
        shift_date  = shift.start_datetime.astimezone(tz).date()
        planned_end = shift.end_datetime.astimezone(tz)
        actual_end_dt = timezone.make_aware(dt_cls.combine(shift_date, dt_time(h, m)), tz)

        duration_minutes = int((planned_end - actual_end_dt).total_seconds() / 60)
        if duration_minutes <= 0:
            return Response({'detail': 'L\'heure réelle doit être antérieure à la fin planifiée.'}, status=status.HTTP_400_BAD_REQUEST)

        adj = TimeAdjustment.objects.create(
            collaborator=shift.collaborator,
            date=shift_date,
            type='early_departure',
            actual_time=actual_end_str,
            reference_time=planned_end.strftime('%H:%M'),
            duration_minutes=duration_minutes,
            shift=shift,
            note=note,
            declared_by=actor,
        )
        return Response(TimeAdjustmentSerializer(adj).data, status=status.HTTP_201_CREATED)


class OvertimeView(APIView):
    """POST /api/planning/shifts/<pk>/overtime/  { duration_minutes, note }"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if not actor or not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            duration_minutes = int(request.data.get('duration_minutes', 0))
        except (ValueError, TypeError):
            return Response({'detail': 'duration_minutes doit être un entier positif.'}, status=status.HTTP_400_BAD_REQUEST)
        if duration_minutes <= 0:
            return Response({'detail': 'La durée doit être positive.'}, status=status.HTTP_400_BAD_REQUEST)

        note = request.data.get('note', '')
        from zoneinfo import ZoneInfo
        tz = ZoneInfo('Europe/Paris')
        shift_date  = shift.start_datetime.astimezone(tz).date()
        planned_end = shift.end_datetime.astimezone(tz)
        actual_end_dt = planned_end + timedelta(minutes=duration_minutes)

        adj = TimeAdjustment.objects.create(
            collaborator=shift.collaborator,
            date=shift_date,
            type='overtime',
            actual_time=actual_end_dt.strftime('%H:%M'),
            reference_time=planned_end.strftime('%H:%M'),
            duration_minutes=duration_minutes,
            shift=shift,
            note=note,
            declared_by=actor,
        )
        return Response(TimeAdjustmentSerializer(adj).data, status=status.HTTP_201_CREATED)


class RCRView(APIView):
    """POST /api/planning/shifts/<pk>/rcr/"""
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        actor = _get_collaborator(request)
        if not actor or not actor.can_manage_planning:
            return Response({'detail': 'Permission insuffisante.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            shift = Shift.objects.get(pk=pk, collaborator__pharmacy=request.user)
        except Shift.DoesNotExist:
            return Response({'detail': 'Shift introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        if not shift.collaborator:
            return Response({'detail': 'Ce shift n\'a pas de collaborateur associé.'}, status=status.HTTP_400_BAD_REQUEST)

        from zoneinfo import ZoneInfo
        shift_date = shift.start_datetime.astimezone(ZoneInfo('Europe/Paris')).date()
        absence = AbsenceRequest.objects.create(
            collaborator=shift.collaborator,
            start_date=shift_date,
            end_date=shift_date,
            type=AbsenceRequest.AbsenceType.RCR,
            status=AbsenceRequest.Status.APPROVED,
            posted_by_manager=True,
        )
        return Response(AbsenceRequestSerializer(absence).data, status=status.HTTP_201_CREATED)
