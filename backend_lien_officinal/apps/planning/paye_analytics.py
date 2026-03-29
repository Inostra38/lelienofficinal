"""
Module de calcul du récap paie CCN Pharmacie.
Utilisé par PayeAnalyticsView pour générer un résumé mensuel.
"""

from datetime import date, datetime, timedelta
import calendar

from django.core.cache import cache

from apps.team.models import Collaborator, ContractHistory
from .models import AbsenceRequest, Shift, TimeAdjustment
from .utils import get_jours_feries, get_label_ferie


FRENCH_MONTHS = [
    '', 'janv', 'févr', 'mars', 'avr', 'mai', 'juin',
    'juil', 'août', 'sept', 'oct', 'nov', 'déc'
]

FRENCH_MONTHS_FULL = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def french_holidays(year: int) -> set:
    return set(get_jours_feries(year))


def count_working_days(year: int, month: int) -> int:
    """Compte les jours ouvrés (Lun-Sam) du mois, hors jours fériés."""
    holidays = french_holidays(year)
    _, last_day = calendar.monthrange(year, month)
    count = 0
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        if d.weekday() <= 5 and d not in holidays:
            count += 1
    return count


def _iso_week_number(d: date) -> int:
    return d.isocalendar()[1]


def format_week_str(monday: date, sunday: date) -> str:
    week_num = _iso_week_number(monday)
    if monday.month == sunday.month:
        return f"S{week_num} — {monday.day} au {sunday.day} {FRENCH_MONTHS[sunday.month]}"
    else:
        return (
            f"S{week_num} — {monday.day} {FRENCH_MONTHS[monday.month]}"
            f" au {sunday.day} {FRENCH_MONTHS[sunday.month]}"
        )


def get_rattached_weeks(year: int, month: int):
    """
    Retourne la liste des semaines rattachées au mois.
    Règle du vendredi : une semaine appartient au mois où tombe son vendredi.
    Retourne (monday, sunday, friday, a_cheval).
    """
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    weeks = []
    seen = set()

    # Semaines dont le vendredi est dans le mois
    d = month_start
    while d <= month_end:
        if d.weekday() == 4:
            friday = d
            monday = friday - timedelta(days=4)
            sunday = friday + timedelta(days=2)
            if monday not in seen:
                seen.add(monday)
                weeks.append((monday, sunday, friday, False))
        d += timedelta(days=1)

    # Semaines à cheval (lundi dans le mois, vendredi dans le mois suivant)
    d = month_start
    while d <= month_end:
        if d.weekday() == 0:
            monday = d
            friday = monday + timedelta(days=4)
            sunday = monday + timedelta(days=6)
            if friday > month_end and monday not in seen:
                seen.add(monday)
                weeks.append((monday, sunday, friday, True))
        d += timedelta(days=1)

    weeks.sort(key=lambda x: x[0])
    return weeks


def get_all_weeks_up_to(from_date: date, to_date: date):
    """Toutes les semaines dont le vendredi est dans [from_date, to_date]."""
    weeks = []
    seen = set()
    d = from_date
    while d.weekday() != 4:
        d += timedelta(days=1)
    while d <= to_date:
        friday = d
        monday = friday - timedelta(days=4)
        sunday = friday + timedelta(days=2)
        if monday not in seen:
            seen.add(monday)
            weeks.append((monday, sunday, friday))
        d += timedelta(days=7)
    return weeks


def hours_overlap(start_dt: datetime, end_dt: datetime, window_start: datetime, window_end: datetime) -> float:
    overlap_start = max(start_dt, window_start)
    overlap_end = min(end_dt, window_end)
    if overlap_end > overlap_start:
        return (overlap_end - overlap_start).total_seconds() / 3600
    return 0.0


def _strip_tz(dt: datetime) -> datetime:
    """Rend un datetime timezone-naive (local time si aware)."""
    if dt is None:
        return dt
    if dt.tzinfo is not None:
        from django.utils import timezone as tz
        return tz.localtime(dt).replace(tzinfo=None)
    return dt


def hours_in_plage(start_dt: datetime, end_dt: datetime, plage_ranges: list) -> float:
    """
    Calcule le total d'heures du shift tombant dans les plages horaires données.
    plage_ranges : liste de (h_start, h_end). Si h_start > h_end → cross-midnight.
    """
    start_dt = _strip_tz(start_dt)
    end_dt   = _strip_tz(end_dt)
    if end_dt <= start_dt:
        return 0.0

    total = 0.0
    current_day = start_dt.date()
    end_day = end_dt.date()

    while current_day <= end_day:
        for (h_start, h_end) in plage_ranges:
            if h_start <= h_end:
                window_start = datetime(current_day.year, current_day.month, current_day.day, h_start)
                window_end   = datetime(current_day.year, current_day.month, current_day.day, h_end)
                total += hours_overlap(start_dt, end_dt, window_start, window_end)
            else:
                # Cross-midnight : h_start → minuit
                window_start = datetime(current_day.year, current_day.month, current_day.day, h_start)
                window_end   = datetime(current_day.year, current_day.month, current_day.day) + timedelta(days=1)
                total += hours_overlap(start_dt, end_dt, window_start, window_end)
                # minuit → h_end du jour suivant
                next_day = current_day + timedelta(days=1)
                window_start2 = datetime(next_day.year, next_day.month, next_day.day, 0, 0)
                window_end2   = datetime(next_day.year, next_day.month, next_day.day, h_end)
                total += hours_overlap(start_dt, end_dt, window_start2, window_end2)
        current_day += timedelta(days=1)

    return total


def sunday_hours(start_dt: datetime, end_dt: datetime) -> float:
    """Heures du shift tombant un dimanche."""
    start_dt = _strip_tz(start_dt)
    end_dt   = _strip_tz(end_dt)
    if end_dt <= start_dt:
        return 0.0

    total = 0.0
    current_day = start_dt.date()
    end_day = end_dt.date()

    while current_day <= end_day:
        if current_day.weekday() == 6:
            day_start = datetime(current_day.year, current_day.month, current_day.day)
            day_end   = day_start + timedelta(days=1)
            total += hours_overlap(start_dt, end_dt, day_start, day_end)
        current_day += timedelta(days=1)

    return total


def shift_duration_hours(shift: Shift) -> float:
    """Durée d'un shift en heures."""
    start = _strip_tz(shift.start_datetime)
    end   = _strip_tz(shift.end_datetime)
    if end <= start:
        return 0.0
    return (end - start).total_seconds() / 3600


def count_working_days_in_range(start: date, end: date) -> int:
    """Jours ouvrés (Lun-Sam) dans [start, end], hors fériés."""
    if end < start:
        return 0
    holidays = set()
    for y in range(start.year, end.year + 1):
        holidays |= french_holidays(y)
    count = 0
    d = start
    while d <= end:
        if d.weekday() <= 5 and d not in holidays:
            count += 1
        d += timedelta(days=1)
    return count


# ── Sous-fonctions ────────────────────────────────────────────────────────────

def _fetch_indexes(pharmacy, full_range_start, full_range_end,
                   month_start, month_end, jan_1) -> dict:
    """Charge toutes les données en bulk et retourne des index par collaborator_id."""
    collaborators = list(
        Collaborator.objects.filter(pharmacy=pharmacy, is_active=True)
        .order_by('display_order', 'id')
    )
    collab_ids = [c.id for c in collaborators]

    all_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        start_datetime__date__gte=full_range_start,
        start_datetime__date__lte=full_range_end,
    ).select_related('collaborator')

    all_month_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=month_start,
        start_datetime__date__lte=month_end,
    ).select_related('collaborator')

    all_absences = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        status='approved',
        start_date__lte=month_end,
        end_date__gte=month_start,
    ).select_related('collaborator')

    all_adjustments = TimeAdjustment.objects.filter(
        collaborator__pharmacy=pharmacy,
        date__gte=full_range_start,
        date__lte=full_range_end,
    ).select_related('collaborator')

    all_annual_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=jan_1,
        start_datetime__date__lte=month_end,
    ).select_related('collaborator')

    all_annual_adjustments = TimeAdjustment.objects.filter(
        collaborator__pharmacy=pharmacy,
        date__gte=jan_1,
        date__lte=month_end,
    ).select_related('collaborator')

    all_annual_rcr = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        status='approved',
        type='rcr',
        start_date__lte=month_end,
        end_date__gte=jan_1,
    ).select_related('collaborator')

    all_annual_formations = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        type='formation',
        status='approved',
        start_date__lte=month_end,
        end_date__gte=jan_1,
    ).select_related('collaborator')

    # Fix N+1 : tous les contrats en une seule requête
    all_contracts = ContractHistory.objects.filter(
        collaborator_id__in=collab_ids,
    ).order_by('collaborator_id', '-start_date')

    def _by_collab(qs):
        d: dict = {}
        for obj in qs:
            d.setdefault(obj.collaborator_id, []).append(obj)
        return d

    contracts_by_collab: dict = {}
    for ct in all_contracts:
        contracts_by_collab.setdefault(ct.collaborator_id, []).append(ct)

    return {
        'collaborators':       collaborators,
        'shifts':              _by_collab(all_shifts),
        'month_shifts':        _by_collab(all_month_shifts),
        'absences':            _by_collab(all_absences),
        'adjustments':         _by_collab(all_adjustments),
        'annual_shifts':       _by_collab(all_annual_shifts),
        'annual_adjustments':  _by_collab(all_annual_adjustments),
        'annual_rcr':          _by_collab(all_annual_rcr),
        'annual_formations':   _by_collab(all_annual_formations),
        'contracts':           contracts_by_collab,
    }


def _resolve_contract(collab, contracts_by_collab: dict, month_end: date):
    """Retourne (is_tns, weekly_hours) depuis ContractHistory préchargé."""
    contracts = contracts_by_collab.get(collab.id, [])
    # contracts ordonnés par -start_date → premier dont start_date <= month_end
    active = next((ct for ct in contracts if ct.start_date <= month_end), None)
    if active:
        return active.contract_type == 'TNS', float(active.weekly_hours)
    return getattr(collab, 'is_tns', False), float(collab.weekly_hours)


def _compute_formation_dates(collab_absences: list, range_start: date, range_end: date) -> set:
    formation_dates: set = set()
    for fa in (a for a in collab_absences if a.type == 'formation'):
        fa_start = max(fa.start_date, range_start)
        fa_end   = min(fa.end_date, range_end)
        d = fa_start
        while d <= fa_end:
            if d.weekday() <= 5:
                formation_dates.add(d)
            d += timedelta(days=1)
    return formation_dates


def _compute_week_detail(monday: date, sunday: date, friday: date, a_cheval: bool,
                          collab_shifts: list, collab_adjustments: list,
                          formation_dates: set, weekly_hours: float):
    """
    Calcule le détail d'une semaine.
    Retourne (week_dict, sup, tr1, tr2, heures_dues_sem).
    """
    week_shifts = [
        s for s in collab_shifts
        if monday <= _strip_tz(s.start_datetime).date() <= sunday
    ]

    heures_shifts_sem  = sum(shift_duration_hours(s) for s in week_shifts if not s.is_absent)
    heures_abs_inj_sem = sum(
        shift_duration_hours(s) for s in week_shifts
        if s.is_absent and s.absence_type == 'injustifiee'
    )

    week_adjs       = [a for a in collab_adjustments if monday <= a.date <= sunday]
    heures_overtime = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'overtime')
    heures_early    = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'early_departure')
    heures_form_sem = sum(7.0 for fd in formation_dates if monday <= fd <= sunday)

    total_semaine = (
        heures_shifts_sem
        + heures_overtime
        + heures_form_sem
        - heures_early
        - heures_abs_inj_sem
    )

    sup  = max(0.0, total_semaine - weekly_hours)
    tr1  = min(sup, 8.0)
    tr2  = max(0.0, sup - 8.0)
    injust_net      = heures_abs_inj_sem + heures_early - heures_overtime
    heures_dues_sem = -max(0.0, injust_net)
    alerte_46h      = total_semaine > 46.0

    day_hours: dict = {}
    for s in week_shifts:
        if not s.is_absent:
            d = _strip_tz(s.start_datetime).date()
            day_hours[d] = day_hours.get(d, 0.0) + shift_duration_hours(s)

    jours_travailles_sem = len(day_hours)
    jours_alerte_10h = [
        {'date': d.isoformat(), 'heures': round(h, 2)}
        for d, h in sorted(day_hours.items()) if h > 10.0
    ]
    alerte_10h = len(jours_alerte_10h) > 0
    alerte_6j  = jours_travailles_sem > 6

    week_dict = {
        'week_str':                   format_week_str(monday, sunday),
        'heures_shifts':              round(heures_shifts_sem, 2),
        'heures_overtime':            round(heures_overtime, 2),
        'heures_early':               round(heures_early, 2),
        'heures_absence_injustifiee': round(heures_abs_inj_sem, 2),
        'heures_formation':           round(heures_form_sem, 2),
        'total_semaine':              round(total_semaine, 2),
        'seuil':                      weekly_hours,
        'sup_tranche1':               round(tr1, 2),
        'sup_tranche2':               round(tr2, 2),
        'heures_dues':                round(heures_dues_sem, 2),
        'alerte_46h':                 alerte_46h,
        'alerte_10h':                 alerte_10h,
        'jours_alerte_10h':           jours_alerte_10h,
        'alerte_6j':                  alerte_6j,
        'jours_travailles_sem':       jours_travailles_sem,
        'rattachement':               f"{FRENCH_MONTHS_FULL[friday.month]} {friday.year}",
        'a_cheval':                   a_cheval,
    }
    return week_dict, sup, tr1, tr2, heures_dues_sem


def _compute_nuit_dimanche(collab_month_shifts: list) -> tuple:
    """Retourne (nuit_20, nuit_40, dimanche) en heures."""
    plage_20 = [(20, 22), (5, 8)]
    plage_40 = [(22, 5)]
    nuit_20 = nuit_40 = dimanche = 0.0
    for s in collab_month_shifts:
        sd = s.start_datetime
        ed = s.end_datetime
        if not isinstance(sd, datetime):
            sd = datetime.combine(sd, datetime.min.time())
        if not isinstance(ed, datetime):
            ed = datetime.combine(ed, datetime.min.time())
        nuit_20  += hours_in_plage(sd, ed, plage_20)
        nuit_40  += hours_in_plage(sd, ed, plage_40)
        dimanche += sunday_hours(sd, ed)
    return nuit_20, nuit_40, dimanche


def _compute_absences_ventilation(collab_absences: list, month_start: date, month_end: date) -> tuple:
    """Retourne (cp, rcr, conge_exc, sans_solde) en jours."""
    cp = rcr = conge_exc = sans_solde = 0
    for absence in collab_absences:
        abs_start = max(absence.start_date, month_start)
        abs_end   = min(absence.end_date, month_end)
        n = count_working_days_in_range(abs_start, abs_end)
        if   absence.type == 'cp':                 cp         += n
        elif absence.type == 'rcr':                rcr        += n
        elif absence.type == 'conge_exceptionnel': conge_exc  += n
        elif absence.type == 'sans_solde':         sans_solde += n
    return cp, rcr, conge_exc, sans_solde


def _compute_feries(collab_month_shifts: list, feries_du_mois: list, year: int) -> tuple:
    """Retourne (jours_list, heures_total)."""
    jours = []
    for f in feries_du_mois:
        shifts_f = [s for s in collab_month_shifts if _strip_tz(s.start_datetime).date() == f]
        if shifts_f:
            heures_f = round(sum(shift_duration_hours(s) for s in shifts_f), 2)
            jours.append({
                'date':        f.isoformat(),
                'label':       get_label_ferie(f, year),
                'heures':      heures_f,
                'premier_mai': f.month == 5 and f.day == 1,
            })
    return jours, round(sum(j['heures'] for j in jours), 2)


def _compute_annuel(collab_id: int, indexes: dict, annual_weeks: list,
                     weekly_hours: float, jan_1: date, month_end: date) -> dict:
    """Calcule les indicateurs annuels RCR + moyenne 44h."""
    collab_annual_shifts     = indexes['annual_shifts'].get(collab_id, [])
    collab_annual_adjustments = indexes['annual_adjustments'].get(collab_id, [])
    collab_annual_rcr        = indexes['annual_rcr'].get(collab_id, [])
    collab_annual_formations = indexes['annual_formations'].get(collab_id, [])

    rcr_acquis_h = 0.0
    weekly_totals: list = []

    for (w_monday, w_sunday, _w_friday) in annual_weeks:
        week_shift_h = sum(
            shift_duration_hours(s)
            for s in collab_annual_shifts
            if w_monday <= _strip_tz(s.start_datetime).date() <= w_sunday
        )
        week_adjs  = [a for a in collab_annual_adjustments if w_monday <= a.date <= w_sunday]
        week_ot    = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'overtime')
        week_early = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'early_departure')

        week_form_h = 0.0
        for fa in (f for f in collab_annual_formations
                   if f.start_date <= w_sunday and f.end_date >= w_monday):
            fa_start = max(fa.start_date, w_monday)
            fa_end   = min(fa.end_date, w_sunday)
            d = fa_start
            while d <= fa_end:
                if d.weekday() <= 5:
                    week_form_h += 7.0
                d += timedelta(days=1)

        week_total = week_shift_h + week_ot - week_early + week_form_h
        rcr_acquis_h += max(0.0, week_total - weekly_hours)
        weekly_totals.append(week_total)

    # CCN art. 13.3.c — moyenne max 44h sur 12 semaines consécutives
    alerte_44h_moy = False
    moy_44h_12sem  = 0.0
    for i in range(len(weekly_totals)):
        window = weekly_totals[max(0, i - 11):i + 1]
        avg = sum(window) / len(window)
        if avg > 44.0:
            alerte_44h_moy = True
        if i == len(weekly_totals) - 1:
            moy_44h_12sem = round(avg, 2)

    rcr_consomme_h = 0.0
    for absence in collab_annual_rcr:
        rcr_start = max(absence.start_date, jan_1)
        rcr_end   = min(absence.end_date, month_end)
        rcr_consomme_h += count_working_days_in_range(rcr_start, rcr_end) * 7.0

    rcr_solde_h = rcr_acquis_h - rcr_consomme_h

    return {
        'rcr_acquis':          round(rcr_acquis_h, 2),
        'rcr_consomme':        round(rcr_consomme_h, 2),
        'rcr_solde':           round(rcr_solde_h, 2),
        'rcr_alerte':          rcr_solde_h > 150.0,
        'rcr_droit_ouvert':    rcr_solde_h >= 7.0,
        'contingent_consomme': round(max(0.0, rcr_solde_h), 2),
        'moy_44h_12sem':       moy_44h_12sem,
        'alerte_44h_moy':      alerte_44h_moy,
    }


# ── Fonction principale ───────────────────────────────────────────────────────

def compute_paye_summary(pharmacy, year: int, month: int) -> dict:
    """
    Calcule le récap paie CCN Pharmacie pour une pharmacie et un mois donnés.
    Les mois entièrement passés sont mis en cache 7 jours.
    """
    today = date.today()
    is_past = (year < today.year) or (year == today.year and month < today.month)
    cache_key = f'paye:{pharmacy.pk}:{year}-{month:02d}'
    if is_past:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, last_day)

    jours_ouvres_mois    = count_working_days(year, month)
    rattached_weeks_all  = get_rattached_weeks(year, month)
    rattached_weeks_main = [(m, s, f) for m, s, f, ac in rattached_weeks_all if not ac]

    range_start      = rattached_weeks_main[0][0]  if rattached_weeks_main else month_start
    range_end        = rattached_weeks_main[-1][1] if rattached_weeks_main else month_end
    full_range_start = rattached_weeks_all[0][0]   if rattached_weeks_all  else month_start
    full_range_end   = rattached_weeks_all[-1][1]  if rattached_weeks_all  else month_end

    nb_weeks_main = len(rattached_weeks_main)
    jan_1         = date(year, 1, 1)
    annual_weeks  = get_all_weeks_up_to(jan_1, month_end)

    feries_annee   = get_jours_feries(year)
    feries_du_mois = [f for f in feries_annee if f.month == month]

    indexes       = _fetch_indexes(pharmacy, full_range_start, full_range_end,
                                   month_start, month_end, jan_1)
    collaborators = indexes['collaborators']

    collaborateurs_data = []
    totaux = dict(
        jours=0, heures_reelles=0.0, heures_sup_total=0.0, heures_dues=0.0,
        nuit_20=0.0, nuit_40=0.0, dimanche=0.0, formation=0.0,
        cp=0, rcr=0, conge_exc=0, sans_solde=0, feries=0.0,
    )

    for collab in collaborators:
        is_tns, weekly_hours = _resolve_contract(collab, indexes['contracts'], month_end)
        initiales = (collab.first_name[:1] + collab.last_name[:1]).upper()
        nom       = f"{collab.first_name} {collab.last_name}"

        collab_shifts       = indexes['shifts'].get(collab.id, [])
        collab_month_shifts = indexes['month_shifts'].get(collab.id, [])
        collab_absences     = indexes['absences'].get(collab.id, [])
        collab_adjustments  = indexes['adjustments'].get(collab.id, [])

        formation_dates  = _compute_formation_dates(collab_absences, range_start, range_end)
        heures_formation = len(formation_dates) * 7.0

        worked_dates = set()
        for s in collab_shifts:
            if not s.is_absent:
                sd = _strip_tz(s.start_datetime).date() if s.start_datetime.tzinfo else s.start_datetime.date()
                if range_start <= sd <= range_end:
                    worked_dates.add(sd)
        jours_travailles = len(worked_dates | formation_dates)

        heures_reelles = sum(
            shift_duration_hours(s) for s in collab_shifts
            if not s.is_absent
            and range_start <= _strip_tz(s.start_datetime).date() <= range_end
        ) + heures_formation

        if is_tns:
            collaborateurs_data.append({
                'id': collab.id, 'nom': nom, 'initiales': initiales,
                'role': collab.get_role_display(), 'is_tns': True,
                'color': collab.color, 'weekly_hours': weekly_hours,
                'jours_travailles': jours_travailles,
                'heures_reelles': round(heures_reelles, 2),
                'heures_contrat': None, 'heures_sup_planning': None,
                'detail_semaines': None, 'heures_dues': None,
                'heures_nuit_20': None, 'heures_nuit_40': None,
                'heures_dimanche': None,
                'heures_formation': round(heures_formation, 2),
                'cp_poses': None, 'rcr_poses': None,
                'conge_exc_poses': None, 'sans_solde_poses': None,
                'heures_feries_travaillees': None,
                'jours_feries_travailles': None, 'annuel': None,
            })
            continue

        # ── Salariés ──────────────────────────────────────────────────────────
        heures_contrat = weekly_hours * nb_weeks_main

        detail_semaines                         = []
        total_sup_tr1 = total_sup_tr2           = 0.0
        total_sup_total = heures_dues_total     = 0.0

        for (monday, sunday, friday, a_cheval) in rattached_weeks_all:
            week_dict, sup, tr1, tr2, dues_sem = _compute_week_detail(
                monday, sunday, friday, a_cheval,
                collab_shifts, collab_adjustments,
                formation_dates, weekly_hours,
            )
            detail_semaines.append(week_dict)
            if not a_cheval:
                total_sup_tr1   += tr1
                total_sup_tr2   += tr2
                total_sup_total += sup
                heures_dues_total += dues_sem

        heures_sup_planning = {
            'total':    round(total_sup_total, 2),
            'tranche1': round(total_sup_tr1, 2),
            'tranche2': round(total_sup_tr2, 2),
        }

        nuit_20, nuit_40, dimanche     = _compute_nuit_dimanche(collab_month_shifts)
        cp, rcr, conge_exc, sans_solde = _compute_absences_ventilation(
            collab_absences, month_start, month_end
        )
        jours_feries_travailles, heures_feries_travaillees = _compute_feries(
            collab_month_shifts, feries_du_mois, year
        )
        annuel = _compute_annuel(
            collab.id, indexes, annual_weeks, weekly_hours, jan_1, month_end
        )

        collaborateurs_data.append({
            'id': collab.id, 'nom': nom, 'initiales': initiales,
            'role': collab.get_role_display(), 'is_tns': False,
            'color': collab.color, 'weekly_hours': weekly_hours,
            'jours_travailles': jours_travailles,
            'heures_reelles': round(heures_reelles, 2),
            'heures_contrat': round(heures_contrat, 2),
            'heures_sup_planning': heures_sup_planning,
            'detail_semaines': detail_semaines,
            'heures_dues': round(heures_dues_total, 2),
            'heures_nuit_20': round(nuit_20, 2),
            'heures_nuit_40': round(nuit_40, 2),
            'heures_dimanche': round(dimanche, 2),
            'heures_formation': round(heures_formation, 2),
            'cp_poses': cp, 'rcr_poses': rcr,
            'conge_exc_poses': conge_exc, 'sans_solde_poses': sans_solde,
            'heures_feries_travaillees': heures_feries_travaillees,
            'jours_feries_travailles': jours_feries_travailles,
            'annuel': annuel,
        })

        totaux['jours']            += jours_travailles
        totaux['heures_reelles']   += heures_reelles
        totaux['heures_sup_total'] += total_sup_total
        totaux['heures_dues']      += heures_dues_total
        totaux['nuit_20']          += nuit_20
        totaux['nuit_40']          += nuit_40
        totaux['dimanche']         += dimanche
        totaux['formation']        += heures_formation
        totaux['cp']               += cp
        totaux['rcr']              += rcr
        totaux['conge_exc']        += conge_exc
        totaux['sans_solde']       += sans_solde
        totaux['feries']           += heures_feries_travaillees

    totaux_salaries = {
        'jours_travailles':           totaux['jours'],
        'heures_reelles':             round(totaux['heures_reelles'], 2),
        'heures_sup_planning_total':  round(totaux['heures_sup_total'], 2),
        'heures_dues':                round(totaux['heures_dues'], 2),
        'heures_nuit_20':             round(totaux['nuit_20'], 2),
        'heures_nuit_40':             round(totaux['nuit_40'], 2),
        'heures_dimanche':            round(totaux['dimanche'], 2),
        'heures_formation':           round(totaux['formation'], 2),
        'cp_poses':                   totaux['cp'],
        'rcr_poses':                  totaux['rcr'],
        'conge_exc_poses':            totaux['conge_exc'],
        'sans_solde_poses':           totaux['sans_solde'],
        'heures_feries_travaillees':  round(totaux['feries'], 2),
    }

    result = {
        'month':             f"{year}-{month:02d}",
        'jours_ouvres_mois': jours_ouvres_mois,
        'collaborateurs':    collaborateurs_data,
        'totaux_salaries':   totaux_salaries,
    }

    if is_past:
        cache.set(cache_key, result, timeout=86400 * 7)  # 7 jours

    return result
