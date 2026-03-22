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

from collections import defaultdict
from datetime import date, timedelta
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


# ── Calcul à partir des données pré-chargées (sans requêtes DB) ──────────────

def _week_summary_from_data(collaborator, monday: date, sunday: date,
                             shifts: list, absences: list, adjustments: list) -> CollaboratorWeekSummary:
    """
    Calcule le résumé hebdomadaire d'un collaborateur à partir de données déjà chargées.
    N'effectue aucune requête DB.
    """
    # ── Résumé shifts ────────────────────────────────────────────────────────
    shift_summaries: list[ShiftSummary] = []
    for s in sorted(shifts, key=lambda x: x.start_datetime):
        dur = _duration_h(s)
        shift_summaries.append(ShiftSummary(
            shift_id=s.id,
            date=s.start_datetime.date().isoformat(),
            start=_format_time(s.start_datetime),
            end=_format_time(s.end_datetime),
            duration_h=dur,
            is_extra_hour=s.is_extra_hour,
            is_published=s.is_published,
        ))

    # Heures contractuelles : snapshot du 1er shift de la semaine si disponible,
    # sinon valeur actuelle du collaborateur (cas semaine vide ou anciens shifts sans snapshot)
    snapshot = next(
        (s.contract_hours_snapshot for s in sorted(shifts, key=lambda x: x.start_datetime)
         if s.contract_hours_snapshot is not None),
        None
    )
    contract_h = float(snapshot) if snapshot is not None else float(collaborator.weekly_hours)
    approved_absences = [a for a in absences if a.status == AbsenceRequest.Status.APPROVED]

    # ── Résumé par jour ──────────────────────────────────────────────────────
    day_summaries: list[DaySummary] = []
    for i in range(7):
        d = monday + timedelta(days=i)
        d_iso = d.isoformat()
        day_shifts = [s for s in shift_summaries if s['date'] == d_iso]
        worked = round(sum(s['duration_h'] for s in day_shifts), 2)

        day_adjs = [a for a in adjustments if a.date == d]
        adj_minutes = 0
        for a in day_adjs:
            if a.type == TimeAdjustment.Type.OVERTIME:
                adj_minutes += a.duration_minutes
            else:
                adj_minutes -= a.duration_minutes
        worked = round(worked + adj_minutes / 60, 2)

        day_summaries.append(DaySummary(
            date=d_iso,
            worked_h=worked,
            absence_type=_absence_on_date(approved_absences, d),
        ))

    planned_h = round(sum(d['worked_h'] for d in day_summaries), 2)

    # ── Heures supplémentaires ───────────────────────────────────────────────
    balance_h  = round(planned_h - contract_h, 2)
    extra_h    = max(0.0, balance_h)
    extra_h_25 = round(min(extra_h, 8.0), 2)
    extra_h_50 = round(max(0.0, extra_h - 8.0), 2)

    # ── Absences (toutes) ────────────────────────────────────────────────────
    absence_summaries: list[AbsenceSummary] = [
        AbsenceSummary(
            absence_id=a.id,
            start_date=a.start_date.isoformat(),
            end_date=a.end_date.isoformat(),
            type=a.type,
            status=a.status,
        )
        for a in absences
    ]

    # ── Ajustements (tous) ───────────────────────────────────────────────────
    adjustment_summaries: list[AdjustmentSummary] = [
        AdjustmentSummary(
            adjustment_id=a.id,
            date=a.date.isoformat(),
            type=a.type,
            actual_time=str(a.actual_time)[:5],
            reference_time=str(a.reference_time)[:5],
            duration_minutes=a.duration_minutes,
            note=a.note,
        )
        for a in adjustments
    ]

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


def week_summary(collaborator, week_start: date) -> CollaboratorWeekSummary:
    """Résumé hebdomadaire d'un seul collaborateur (effectue 3 requêtes DB)."""
    monday, sunday = _week_bounds(week_start)
    shifts = list(Shift.objects.filter(
        collaborator=collaborator,
        start_datetime__date__gte=monday,
        start_datetime__date__lte=sunday,
    ))
    absences = list(AbsenceRequest.objects.filter(
        collaborator=collaborator,
        start_date__lte=sunday,
        end_date__gte=monday,
    ))
    adjustments = list(TimeAdjustment.objects.filter(
        collaborator=collaborator,
        date__gte=monday,
        date__lte=sunday,
    ))
    return _week_summary_from_data(collaborator, monday, sunday, shifts, absences, adjustments)


# ── Résumé pharmacie (batch — 3 requêtes quelle que soit la taille de l'équipe) ─

def pharmacy_week_summary(pharmacy, week_start: date) -> list[CollaboratorWeekSummary]:
    """
    Résumé hebdomadaire pour toute l'équipe.
    Effectue exactement 5 requêtes DB indépendamment du nombre de collaborateurs.
    """
    from apps.team.models import Collaborator  # évite les circular imports

    monday, sunday = _week_bounds(week_start)

    # Collaborateurs actifs
    active_collabs = list(
        Collaborator.objects.filter(pharmacy=pharmacy, is_active=True)
        .order_by('display_order', 'id')
    )
    active_ids = {c.id for c in active_collabs}

    # Collaborateurs archivés avec shifts publiés cette semaine
    archived_with_shifts = list(
        Collaborator.objects.filter(
            pharmacy=pharmacy,
            is_active=False,
            shifts__start_datetime__date__gte=monday,
            shifts__start_datetime__date__lte=sunday,
            shifts__is_published=True,
        ).exclude(id__in=active_ids).distinct().order_by('display_order', 'id')
    )

    all_collabs = active_collabs + archived_with_shifts
    if not all_collabs:
        return []

    all_ids = [c.id for c in all_collabs]

    # ── 3 requêtes batch ─────────────────────────────────────────────────────

    shifts_by_collab: dict[int, list] = defaultdict(list)
    for s in Shift.objects.filter(
        collaborator_id__in=all_ids,
        start_datetime__date__gte=monday,
        start_datetime__date__lte=sunday,
    ).select_related('collaborator'):
        shifts_by_collab[s.collaborator_id].append(s)

    absences_by_collab: dict[int, list] = defaultdict(list)
    for a in AbsenceRequest.objects.filter(
        collaborator_id__in=all_ids,
        start_date__lte=sunday,
        end_date__gte=monday,
    ):
        absences_by_collab[a.collaborator_id].append(a)

    adjustments_by_collab: dict[int, list] = defaultdict(list)
    for adj in TimeAdjustment.objects.filter(
        collaborator_id__in=all_ids,
        date__gte=monday,
        date__lte=sunday,
    ):
        adjustments_by_collab[adj.collaborator_id].append(adj)

    # ── Calcul (aucune requête DB supplémentaire) ────────────────────────────
    return [
        _week_summary_from_data(
            c, monday, sunday,
            shifts_by_collab[c.id],
            absences_by_collab[c.id],
            adjustments_by_collab[c.id],
        )
        for c in all_collabs
    ]
