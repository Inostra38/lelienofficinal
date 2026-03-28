"""
Module de calcul du récap paie CCN Pharmacie.
Utilisé par PayeAnalyticsView pour générer un résumé mensuel.
"""

from datetime import date, datetime, timedelta
import calendar

from apps.team.models import Collaborator
from .models import AbsenceRequest, Shift, TimeAdjustment
from .utils import get_jours_feries, get_label_ferie


# ── Palette couleurs collaborateurs ──────────────────────────────────────────

COLOR_MAP = {
    'green':   ('#dcfce7', '#14532d'),
    'emerald': ('#d1fae5', '#064e3b'),
    'teal':    ('#ccfbf1', '#134e4a'),
    'cyan':    ('#cffafe', '#164e63'),
    'sky':     ('#e0f2fe', '#0c4a6e'),
    'blue':    ('#dbeafe', '#1e3a8a'),
    'indigo':  ('#e0e7ff', '#312e81'),
    'violet':  ('#ede9fe', '#2e1065'),
    'purple':  ('#f3e8ff', '#4c1d95'),
    'fuchsia': ('#fae8ff', '#701a75'),
    'pink':    ('#fce7f3', '#831843'),
    'rose':    ('#ffe4e6', '#881337'),
    'red':     ('#fee2e2', '#7f1d1d'),
    'orange':  ('#ffedd5', '#7c2d12'),
    'amber':   ('#fef3c7', '#78350f'),
    'yellow':  ('#fef9c3', '#713f12'),
    'lime':    ('#f7fee7', '#1a2e05'),
    'slate':   ('#f1f5f9', '#0f172a'),
    'gray':    ('#f3f4f6', '#1f2937'),
}

FRENCH_MONTHS = [
    '', 'janv', 'févr', 'mars', 'avr', 'mai', 'juin',
    'juil', 'août', 'sept', 'oct', 'nov', 'déc'
]

FRENCH_MONTHS_FULL = [
    '', 'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_collaborator_color(color_name: str):
    """Retourne (bg_hex, text_hex) pour la couleur donnée."""
    return COLOR_MAP.get(color_name, COLOR_MAP['blue'])


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


# ── Fonction principale ───────────────────────────────────────────────────────

def compute_paye_summary(pharmacy, year: int, month: int) -> dict:
    """
    Calcule le récap paie CCN Pharmacie pour une pharmacie et un mois donnés.
    """
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end   = date(year, month, last_day)

    jours_ouvres_mois = count_working_days(year, month)

    rattached_weeks_all  = get_rattached_weeks(year, month)
    rattached_weeks_main = [(m, s, f) for m, s, f, ac in rattached_weeks_all if not ac]

    if rattached_weeks_main:
        range_start = rattached_weeks_main[0][0]
        range_end   = rattached_weeks_main[-1][1]
    else:
        range_start = month_start
        range_end   = month_end

    if rattached_weeks_all:
        full_range_start = rattached_weeks_all[0][0]
        full_range_end   = rattached_weeks_all[-1][1]
    else:
        full_range_start = month_start
        full_range_end   = month_end

    nb_weeks_main = len(rattached_weeks_main)

    collaborators = Collaborator.objects.filter(
        pharmacy=pharmacy,
        is_active=True,
    ).order_by('display_order', 'id')

    # Tous les shifts publiés dans la plage (y compris absents pour détection injustifiée)
    all_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        start_datetime__date__gte=full_range_start,
        start_datetime__date__lte=full_range_end,
    ).select_related('collaborator')

    # Shifts non-absents du mois civil (nuit, dimanche, fériés)
    all_month_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=month_start,
        start_datetime__date__lte=month_end,
    ).select_related('collaborator')

    # Absences approuvées du mois civil
    all_absences = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        status='approved',
        start_date__lte=month_end,
        end_date__gte=month_start,
    ).select_related('collaborator')

    # Ajustements du mois civil
    all_adjustments = TimeAdjustment.objects.filter(
        collaborator__pharmacy=pharmacy,
        date__gte=full_range_start,
        date__lte=full_range_end,
    ).select_related('collaborator')

    # Données annuelles pour RCR
    jan_1 = date(year, 1, 1)
    annual_weeks = get_all_weeks_up_to(jan_1, month_end)

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

    # Jours fériés du mois
    feries_annee  = get_jours_feries(year)
    feries_du_mois = [f for f in feries_annee if f.month == month]

    # Index par collaborateur
    shifts_by_collab = {}
    for shift in all_shifts:
        shifts_by_collab.setdefault(shift.collaborator_id, []).append(shift)

    month_shifts_by_collab = {}
    for shift in all_month_shifts:
        month_shifts_by_collab.setdefault(shift.collaborator_id, []).append(shift)

    absences_by_collab = {}
    for absence in all_absences:
        absences_by_collab.setdefault(absence.collaborator_id, []).append(absence)

    adjustments_by_collab = {}
    for adj in all_adjustments:
        adjustments_by_collab.setdefault(adj.collaborator_id, []).append(adj)

    annual_shifts_by_collab = {}
    for shift in all_annual_shifts:
        annual_shifts_by_collab.setdefault(shift.collaborator_id, []).append(shift)

    annual_adjustments_by_collab = {}
    for adj in all_annual_adjustments:
        annual_adjustments_by_collab.setdefault(adj.collaborator_id, []).append(adj)

    annual_rcr_by_collab = {}
    for absence in all_annual_rcr:
        annual_rcr_by_collab.setdefault(absence.collaborator_id, []).append(absence)

    # BLOC 3 — pré-chargement formations annuelles : évite N*52 requêtes dans la boucle RCR
    all_annual_formations = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        type='formation',
        status='approved',
        start_date__lte=month_end,
        end_date__gte=jan_1,
    ).select_related('collaborator')

    annual_formations_by_collab = {}
    for absence in all_annual_formations:
        annual_formations_by_collab.setdefault(absence.collaborator_id, []).append(absence)

    collaborateurs_data = []

    totaux_jours            = 0
    totaux_heures_reelles   = 0.0
    totaux_heures_sup_total = 0.0
    totaux_heures_dues      = 0.0
    totaux_nuit_20          = 0.0
    totaux_nuit_40          = 0.0
    totaux_dimanche         = 0.0
    totaux_formation        = 0.0
    totaux_cp               = 0
    totaux_rcr              = 0
    totaux_conge_exc        = 0
    totaux_sans_solde       = 0
    totaux_feries           = 0.0

    for collab in collaborators:
        # Contrat actif au dernier jour du mois (source de vérité pour TNS + heures)
        active_contract = collab.active_contract_on(month_end)
        if active_contract:
            is_tns       = active_contract.contract_type == 'TNS'
            weekly_hours = float(active_contract.weekly_hours)
        else:
            is_tns       = getattr(collab, 'is_tns', False)
            weekly_hours = float(collab.weekly_hours)

        bg_hex, text_hex = get_collaborator_color(collab.color)
        initiales = (collab.first_name[:1] + collab.last_name[:1]).upper()
        nom       = f"{collab.first_name} {collab.last_name}"

        collab_shifts      = shifts_by_collab.get(collab.id, [])
        collab_month_shifts = month_shifts_by_collab.get(collab.id, [])
        collab_absences    = absences_by_collab.get(collab.id, [])
        collab_adjustments = adjustments_by_collab.get(collab.id, [])

        # Jours de formation (Lun-Sam) dans la plage rattachée
        formation_absences = [a for a in collab_absences if a.type == 'formation']
        formation_dates = set()
        for fa in formation_absences:
            fa_start = max(fa.start_date, range_start)
            fa_end   = min(fa.end_date, range_end)
            d = fa_start
            while d <= fa_end:
                if d.weekday() <= 5:
                    formation_dates.add(d)
                d += timedelta(days=1)
        heures_formation = len(formation_dates) * 7.0

        # Jours travaillés (non-absent shifts dans plage + formation)
        worked_dates = set()
        for shift in collab_shifts:
            if not shift.is_absent:
                shift_date = _strip_tz(shift.start_datetime).date() if shift.start_datetime.tzinfo else shift.start_datetime.date()
                if range_start <= shift_date <= range_end:
                    worked_dates.add(shift_date)
        jours_travailles = len(worked_dates | formation_dates)

        # Heures réelles (non-absent dans plage + formation)
        heures_reelles = sum(
            shift_duration_hours(s) for s in collab_shifts
            if not s.is_absent
            and range_start <= _strip_tz(s.start_datetime).date() <= range_end
        ) + heures_formation

        if is_tns:
            collaborateurs_data.append({
                'id': collab.id,
                'nom': nom,
                'initiales': initiales,
                'role': collab.get_role_display(),
                'is_tns': True,
                'color': collab.color,
                'weekly_hours': weekly_hours,
                'jours_travailles': jours_travailles,
                'heures_reelles': round(heures_reelles, 2),
                'heures_contrat': None,
                'heures_sup_planning': None,
                'detail_semaines': None,
                'heures_dues': None,
                'heures_nuit_20': None,
                'heures_nuit_40': None,
                'heures_dimanche': None,
                'heures_formation': round(heures_formation, 2),
                'cp_poses':          None,
                'rcr_poses':         None,
                'conge_exc_poses':   None,
                'sans_solde_poses':  None,
                'heures_feries_travaillees': None,
                'jours_feries_travailles': None,
                'annuel': None,
            })
            continue

        # ── Salariés ──────────────────────────────────────────────────────────

        heures_contrat = weekly_hours * nb_weeks_main

        # Calcul semaine par semaine
        detail_semaines = []
        total_sup_tr1   = 0.0
        total_sup_tr2   = 0.0
        total_sup_total = 0.0
        heures_dues_total = 0.0

        for (monday, sunday, friday, a_cheval) in rattached_weeks_all:
            week_shifts = [
                s for s in collab_shifts
                if monday <= _strip_tz(s.start_datetime).date() <= sunday
            ]

            # Heures de shifts non-absents
            heures_shifts_sem = sum(
                shift_duration_hours(s) for s in week_shifts if not s.is_absent
            )

            # Heures d'absences injustifiées au niveau shift (déduction)
            heures_abs_inj_sem = sum(
                shift_duration_hours(s) for s in week_shifts
                if s.is_absent and s.absence_type == 'injustifiee'
            )

            # Ajustements de la semaine
            week_adjs = [a for a in collab_adjustments if monday <= a.date <= sunday]
            heures_overtime = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'overtime')
            heures_early    = sum(a.duration_minutes / 60 for a in week_adjs if a.type == 'early_departure')

            # Formation de la semaine
            heures_formation_sem = sum(7.0 for fd in formation_dates if monday <= fd <= sunday)

            # Total effectif de la semaine
            total_semaine = (
                heures_shifts_sem
                + heures_overtime
                + heures_formation_sem
                - heures_early
                - heures_abs_inj_sem
            )

            sup = max(0.0, total_semaine - weekly_hours)
            tr1 = min(sup, 8.0)
            tr2 = max(0.0, sup - 8.0)
            # heures_dues : uniquement le déficit dû à des raisons injustifiées
            # (absences injust. + départs anticipés non compensés par overtime)
            injust_net = heures_abs_inj_sem + heures_early - heures_overtime
            heures_dues_sem = -max(0.0, injust_net)
            alerte_46h = total_semaine > 46.0

            # CCN art. 13.3.b — durée quotidienne max 10h
            day_hours: dict[date, float] = {}
            for s in week_shifts:
                if not s.is_absent:
                    d = _strip_tz(s.start_datetime).date()
                    day_hours[d] = day_hours.get(d, 0.0) + shift_duration_hours(s)
            jours_travailles_sem = len(day_hours)
            jours_alerte_10h = [
                {'date': d.isoformat(), 'heures': round(h, 2)}
                for d, h in sorted(day_hours.items())
                if h > 10.0
            ]
            alerte_10h = len(jours_alerte_10h) > 0

            # CCN art. 13.4.b — max 6 jours/semaine
            alerte_6j = jours_travailles_sem > 6

            rattachement = f"{FRENCH_MONTHS_FULL[friday.month]} {friday.year}"

            detail_semaines.append({
                'week_str':                  format_week_str(monday, sunday),
                'heures_shifts':             round(heures_shifts_sem, 2),
                'heures_overtime':           round(heures_overtime, 2),
                'heures_early':              round(heures_early, 2),
                'heures_absence_injustifiee': round(heures_abs_inj_sem, 2),
                'heures_formation':          round(heures_formation_sem, 2),
                'total_semaine':             round(total_semaine, 2),
                'seuil':                     weekly_hours,
                'sup_tranche1':              round(tr1, 2),
                'sup_tranche2':              round(tr2, 2),
                'heures_dues':               round(heures_dues_sem, 2),
                'alerte_46h':                alerte_46h,
                'alerte_10h':                alerte_10h,
                'jours_alerte_10h':          jours_alerte_10h,
                'alerte_6j':                 alerte_6j,
                'jours_travailles_sem':      jours_travailles_sem,
                'rattachement':              rattachement,
                'a_cheval':                  a_cheval,
            })

            if not a_cheval:
                total_sup_tr1   += tr1
                total_sup_tr2   += tr2
                total_sup_total += sup
                heures_dues_total += heures_dues_sem

        heures_sup_planning = {
            'total':    round(total_sup_total, 2),
            'tranche1': round(total_sup_tr1, 2),
            'tranche2': round(total_sup_tr2, 2),
        }

        # Nuit et dimanche (mois civil, non-absent)
        plage_20 = [(20, 22), (5, 8)]
        plage_40 = [(22, 5)]
        heures_nuit_20 = 0.0
        heures_nuit_40 = 0.0
        heures_dimanche = 0.0

        for shift in collab_month_shifts:
            sd = shift.start_datetime
            ed = shift.end_datetime
            if not isinstance(sd, datetime):
                sd = datetime.combine(sd, datetime.min.time())
            if not isinstance(ed, datetime):
                ed = datetime.combine(ed, datetime.min.time())
            heures_nuit_20  += hours_in_plage(sd, ed, plage_20)
            heures_nuit_40  += hours_in_plage(sd, ed, plage_40)
            heures_dimanche += sunday_hours(sd, ed)

        # Absences du mois civil — ventilation par type
        cp_poses          = 0
        rcr_poses         = 0
        conge_exc_poses   = 0
        sans_solde_poses  = 0
        for absence in collab_absences:
            abs_start = max(absence.start_date, month_start)
            abs_end   = min(absence.end_date, month_end)
            n_days    = count_working_days_in_range(abs_start, abs_end)
            if   absence.type == 'cp':                cp_poses         += n_days
            elif absence.type == 'rcr':               rcr_poses        += n_days
            elif absence.type == 'conge_exceptionnel': conge_exc_poses  += n_days
            elif absence.type == 'sans_solde':        sans_solde_poses += n_days

        # Jours fériés travaillés (shifts non-absents ce jour)
        jours_feries_travailles = []
        for f in feries_du_mois:
            shifts_ferie = [s for s in collab_month_shifts if _strip_tz(s.start_datetime).date() == f]
            if shifts_ferie:
                heures_f = round(sum(shift_duration_hours(s) for s in shifts_ferie), 2)
                jours_feries_travailles.append({
                    'date':       f.isoformat(),
                    'label':      get_label_ferie(f, year),
                    'heures':     heures_f,
                    'premier_mai': f.month == 5 and f.day == 1,
                })
        heures_feries_travaillees = round(sum(j['heures'] for j in jours_feries_travailles), 2)

        # ── Calcul annuel RCR ──────────────────────────────────────────────────
        collab_annual_shifts      = annual_shifts_by_collab.get(collab.id, [])
        collab_annual_adjustments = annual_adjustments_by_collab.get(collab.id, [])
        collab_annual_rcr         = annual_rcr_by_collab.get(collab.id, [])

        rcr_acquis_h = 0.0
        weekly_totals_annuel: list[float] = []
        for (w_monday, w_sunday, w_friday) in annual_weeks:
            week_shift_h = sum(
                shift_duration_hours(s)
                for s in collab_annual_shifts
                if w_monday <= _strip_tz(s.start_datetime).date() <= w_sunday
            )
            week_adjs_annual = [a for a in collab_annual_adjustments if w_monday <= a.date <= w_sunday]
            week_ot_annual   = sum(a.duration_minutes / 60 for a in week_adjs_annual if a.type == 'overtime')
            week_early_annual = sum(a.duration_minutes / 60 for a in week_adjs_annual if a.type == 'early_departure')

            week_form_h = 0.0
            collab_annual_formations = annual_formations_by_collab.get(collab.id, [])
            for fa in [f for f in collab_annual_formations if f.start_date <= w_sunday and f.end_date >= w_monday]:
                fa_start = max(fa.start_date, w_monday)
                fa_end   = min(fa.end_date, w_sunday)
                d = fa_start
                while d <= fa_end:
                    if d.weekday() <= 5:
                        week_form_h += 7.0
                    d += timedelta(days=1)

            week_total_annuel = week_shift_h + week_ot_annual - week_early_annual + week_form_h
            week_sup = max(0.0, week_total_annuel - weekly_hours)
            rcr_acquis_h += week_sup
            weekly_totals_annuel.append(week_total_annuel)

        # CCN art. 13.3.c — moyenne max 44h sur toute période de 12 semaines consécutives
        alerte_44h_moy = False
        moy_44h_12sem  = 0.0
        for i in range(len(weekly_totals_annuel)):
            window = weekly_totals_annuel[max(0, i - 11):i + 1]
            avg = sum(window) / len(window)
            if avg > 44.0:
                alerte_44h_moy = True
            if i == len(weekly_totals_annuel) - 1:
                moy_44h_12sem = round(avg, 2)

        rcr_consomme_h = 0.0
        for absence in collab_annual_rcr:
            rcr_start = max(absence.start_date, jan_1)
            rcr_end   = min(absence.end_date, month_end)
            rcr_consomme_h += count_working_days_in_range(rcr_start, rcr_end) * 7.0

        rcr_solde_h = rcr_acquis_h - rcr_consomme_h
        rcr_alerte  = rcr_solde_h > 150.0
        # Contingent = heures sup NON compensées par RCR (CCN art. 13.2.d)
        contingent_h = max(0.0, rcr_solde_h)

        annuel = {
            'rcr_acquis':          round(rcr_acquis_h, 2),
            'rcr_consomme':        round(rcr_consomme_h, 2),
            'rcr_solde':           round(rcr_solde_h, 2),
            'rcr_alerte':          rcr_alerte,
            'rcr_droit_ouvert':    rcr_solde_h >= 7.0,
            'contingent_consomme': round(contingent_h, 2),
            'moy_44h_12sem':       moy_44h_12sem,
            'alerte_44h_moy':      alerte_44h_moy,
        }

        collaborateurs_data.append({
            'id': collab.id,
            'nom': nom,
            'initiales': initiales,
            'role': collab.get_role_display(),
            'is_tns': False,
            'color': collab.color,
            'weekly_hours': weekly_hours,
            'jours_travailles': jours_travailles,
            'heures_reelles': round(heures_reelles, 2),
            'heures_contrat': round(heures_contrat, 2),
            'heures_sup_planning': heures_sup_planning,
            'detail_semaines': detail_semaines,
            'heures_dues': round(heures_dues_total, 2),
            'heures_nuit_20': round(heures_nuit_20, 2),
            'heures_nuit_40': round(heures_nuit_40, 2),
            'heures_dimanche': round(heures_dimanche, 2),
            'heures_formation': round(heures_formation, 2),
            'cp_poses':          cp_poses,
            'rcr_poses':         rcr_poses,
            'conge_exc_poses':   conge_exc_poses,
            'sans_solde_poses':  sans_solde_poses,
            'heures_feries_travaillees': heures_feries_travaillees,
            'jours_feries_travailles': jours_feries_travailles,
            'annuel': annuel,
        })

        totaux_jours            += jours_travailles
        totaux_heures_reelles   += heures_reelles
        totaux_heures_sup_total += total_sup_total
        totaux_heures_dues      += heures_dues_total
        totaux_nuit_20          += heures_nuit_20
        totaux_nuit_40          += heures_nuit_40
        totaux_dimanche         += heures_dimanche
        totaux_formation        += heures_formation
        totaux_cp               += cp_poses
        totaux_rcr              += rcr_poses
        totaux_conge_exc        += conge_exc_poses
        totaux_sans_solde       += sans_solde_poses
        totaux_feries           += heures_feries_travaillees

    totaux_salaries = {
        'jours_travailles':         totaux_jours,
        'heures_reelles':           round(totaux_heures_reelles, 2),
        'heures_sup_planning_total': round(totaux_heures_sup_total, 2),
        'heures_dues':              round(totaux_heures_dues, 2),
        'heures_nuit_20':           round(totaux_nuit_20, 2),
        'heures_nuit_40':           round(totaux_nuit_40, 2),
        'heures_dimanche':          round(totaux_dimanche, 2),
        'heures_formation':         round(totaux_formation, 2),
        'cp_poses':                 totaux_cp,
        'rcr_poses':                totaux_rcr,
        'conge_exc_poses':          totaux_conge_exc,
        'sans_solde_poses':         totaux_sans_solde,
        'heures_feries_travaillees': round(totaux_feries, 2),
    }

    return {
        'month':             f"{year}-{month:02d}",
        'jours_ouvres_mois': jours_ouvres_mois,
        'collaborateurs':    collaborateurs_data,
        'totaux_salaries':   totaux_salaries,
    }
