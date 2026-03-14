"""
Convention Collective Nationale des Pharmacies d'Officine (IDCC 1996)
Calcul des heures travaillées, supplémentaires et récapitulatif hebdomadaire.

Règles appliquées :
- Semaine = lundi au dimanche
- Seuil légal : 35h/semaine (configurable via weekly_hours sur le collaborateur)
- Heures supplémentaires : au-delà du seuil contractuel
- Majoration : 25% pour les 8 premières heures sup, 50% au-delà (art. L3121-36 C. trav.)
- Durée max journée : 10h (validé côté modèle Shift.clean)
- Repos quotidien : 11h minimum (validé côté modèle Shift.clean)
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import TypedDict

from apps.planning.models import AbsenceRequest, Shift, TimeAdjustment


# ── Types ───────────────────────────────────────────────────────────────────

class ShiftSummary(TypedDict):
    shift_id: int
    date: str          # ISO
    start: str         # "HH:MM"
    end: str           # "HH:MM"
    duration_h: float
    is_extra_hour: bool
    is_published: bool


class DaySummary(TypedDict):
    date: str          # ISO
    worked_h: float
    absence_type: str | None   # cp / maladie / rcr / sans_solde ou None


class AbsenceSummary(TypedDict):
    absence_id: int
    start_date: str
    end_date: str
    type: str
    status: str        # pending / approved / rejected


class AdjustmentSummary(TypedDict):
    adjustment_id: int
    date: str
    type: str
    actual_time: str
    reference_time: str
    duration_minutes: int
    note: str


class CollaboratorWeekSummary(TypedDict):
    collaborator_id: int
    full_name: str
    role: str
    color: str
    contract_hours: float      # heures contractuelles hebdo
    planned_h: float           # total heures planifiées (shifts + ajustements)
    extra_h: float             # heures au-delà du seuil contractuel
    extra_h_25: float          # heures sup majorées à 25%
    extra_h_50: float          # heures sup majorées à 50%
    balance_h: float           # planned - contract (négatif = sous-temps)
    shifts: list[ShiftSummary]
    days: list[DaySummary]
    absences: list[AbsenceSummary]
    adjustments: list[AdjustmentSummary]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _week_bounds(week_start: date) -> tuple[date, date]:
    """Retourne (lundi, dimanche) de la semaine contenant week_start."""
    monday = week_start - timedelta(days=week_start.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _format_time(dt) -> str:
    return dt.strftime('%H:%M')


def _duration_h(shift: Shift) -> float:
    delta = shift.end_datetime - shift.start_datetime
    return round(delta.total_seconds() / 3600, 2)


def _absence_on_date(absences, d: date) -> str | None:
    for a in absences:
        if a.status == AbsenceRequest.Status.APPROVED and a.start_date <= d <= a.end_date:
            return a.type
    return None


# ── Calcul par collaborateur ─────────────────────────────────────────────────

def week_summary(collaborator, week_start: date) -> CollaboratorWeekSummary:
    """
    Retourne le résumé hebdomadaire complet d'un collaborateur.

    :param collaborator: instance de team.Collaborator
    :param week_start:   n'importe quel jour de la semaine cible (sera normalisé au lundi)
    """
    monday, sunday = _week_bounds(week_start)

    # Shifts de la semaine
    shifts_qs = Shift.objects.filter(
        collaborator=collaborator,
        start_datetime__date__gte=monday,
        start_datetime__date__lte=sunday,
    ).order_by('start_datetime')

    # Absences qui chevauchent la semaine (tous statuts — filtré ensuite)
    absences_qs = AbsenceRequest.objects.filter(
        collaborator=collaborator,
        start_date__lte=sunday,
        end_date__gte=monday,
    )

    # Ajustements horaires (heures sup / départ anticipé)
    adjustments_qs = TimeAdjustment.objects.filter(
        collaborator=collaborator,
        date__gte=monday,
        date__lte=sunday,
    )

    # ── Résumé shifts ────────────────────────────────────────────────────────
    shift_summaries: list[ShiftSummary] = []
    shifts_total_h = 0.0

    for s in shifts_qs:
        dur = _duration_h(s)
        shifts_total_h += dur
        shift_summaries.append(ShiftSummary(
            shift_id=s.id,
            date=s.start_datetime.date().isoformat(),
            start=_format_time(s.start_datetime),
            end=_format_time(s.end_datetime),
            duration_h=dur,
            is_extra_hour=s.is_extra_hour,
            is_published=s.is_published,
        ))

    contract_h = float(collaborator.weekly_hours)

    # ── Résumé par jour ──────────────────────────────────────────────────────
    day_summaries: list[DaySummary] = []
    approved_absences = [a for a in absences_qs if a.status == AbsenceRequest.Status.APPROVED]

    for i in range(7):
        d = monday + timedelta(days=i)
        day_shifts = [s for s in shift_summaries if s['date'] == d.isoformat()]
        worked = round(sum(s['duration_h'] for s in day_shifts), 2)

        # Appliquer les ajustements du jour
        day_adjs = [a for a in adjustments_qs if a.date == d]
        adj_minutes = 0
        for a in day_adjs:
            if a.type == TimeAdjustment.Type.OVERTIME:
                adj_minutes += a.duration_minutes
            else:  # early_departure
                adj_minutes -= a.duration_minutes
        worked = round(worked + adj_minutes / 60, 2)

        day_summaries.append(DaySummary(
            date=d.isoformat(),
            worked_h=worked,
            absence_type=_absence_on_date(approved_absences, d),
        ))

    # planned_h = total des heures travaillées (shifts + ajustements)
    planned_h = round(sum(d['worked_h'] for d in day_summaries), 2)

    # ── Heures supplémentaires (Convention Collective) ───────────────────────
    balance_h = round(planned_h - contract_h, 2)
    extra_h   = max(0.0, balance_h)

    # Majoration : 25% sur les 8 premières heures sup, 50% au-delà
    extra_h_25 = round(min(extra_h, 8.0), 2)
    extra_h_50 = round(max(0.0, extra_h - 8.0), 2)

    # ── Absences (toutes) ────────────────────────────────────────────────────
    absence_summaries: list[AbsenceSummary] = []
    for a in absences_qs:
        absence_summaries.append(AbsenceSummary(
            absence_id=a.id,
            start_date=a.start_date.isoformat(),
            end_date=a.end_date.isoformat(),
            type=a.type,
            status=a.status,
        ))

    # ── Ajustements (tous) ────────────────────────────────────────────────────
    adjustment_summaries: list[AdjustmentSummary] = []
    for a in adjustments_qs:
        adjustment_summaries.append(AdjustmentSummary(
            adjustment_id=a.id,
            date=a.date.isoformat(),
            type=a.type,
            actual_time=str(a.actual_time)[:5],
            reference_time=str(a.reference_time)[:5],
            duration_minutes=a.duration_minutes,
            note=a.note,
        ))

    return CollaboratorWeekSummary(
        collaborator_id=collaborator.id,
        full_name=f"{collaborator.first_name} {collaborator.last_name}",
        role=collaborator.role,
        color=collaborator.color,
        contract_hours=contract_h,
        planned_h=planned_h,
        extra_h=extra_h,
        extra_h_25=extra_h_25,
        extra_h_50=extra_h_50,
        balance_h=balance_h,
        shifts=shift_summaries,
        days=day_summaries,
        absences=absence_summaries,
        adjustments=adjustment_summaries,
    )


# ── Résumé pharmacie ─────────────────────────────────────────────────────────

def pharmacy_week_summary(pharmacy, week_start: date) -> list[CollaboratorWeekSummary]:
    """
    Résumé hebdomadaire pour toute l'équipe d'une pharmacie.

    :param pharmacy:   instance du modèle User (pharmacie)
    :param week_start: n'importe quel jour de la semaine cible
    """
    from apps.team.models import Collaborator  # import local pour éviter les circular imports

    monday, sunday = _week_bounds(week_start)

    # Collaborateurs actifs
    active_collabs = list(
        Collaborator.objects.filter(pharmacy=pharmacy, is_active=True)
        .order_by('display_order', 'id')
    )
    active_ids = {c.id for c in active_collabs}

    # Collaborateurs archivés ayant des shifts publiés dans cette semaine
    # (préserve l'historique des semaines déjà publiées)
    archived_with_shifts = list(
        Collaborator.objects.filter(
            pharmacy=pharmacy,
            is_active=False,
            shifts__start_datetime__date__gte=monday,
            shifts__start_datetime__date__lte=sunday,
            shifts__is_published=True,
        ).exclude(id__in=active_ids).distinct().order_by('display_order', 'id')
    )

    return [week_summary(c, week_start) for c in active_collabs + archived_with_shifts]
