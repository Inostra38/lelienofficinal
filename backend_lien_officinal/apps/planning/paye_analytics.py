"""
Module de calcul du récap paie CCN Pharmacie.
Utilisé par PayeAnalyticsView pour générer un résumé mensuel.
"""

from datetime import date, datetime, timedelta
import calendar

from apps.team.models import Collaborator
from .models import AbsenceRequest, Shift, TimeAdjustment


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
    """
    Retourne l'ensemble des jours fériés français pour l'année donnée.
    Utilise l'algorithme de Gauss pour Pâques.
    """
    # Algorithme de Gauss pour calculer la date de Pâques
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    easter = date(year, month, day)

    holidays = set()

    # Fêtes fixes
    holidays.add(date(year, 1, 1))   # Jour de l'An
    holidays.add(date(year, 5, 1))   # Fête du Travail
    holidays.add(date(year, 5, 8))   # Victoire 1945
    holidays.add(date(year, 7, 14))  # Fête Nationale
    holidays.add(date(year, 8, 15))  # Assomption
    holidays.add(date(year, 11, 1))  # Toussaint
    holidays.add(date(year, 11, 11)) # Armistice
    holidays.add(date(year, 12, 25)) # Noël

    # Fêtes mobiles (liées à Pâques)
    holidays.add(easter + timedelta(days=1))   # Lundi de Pâques
    holidays.add(easter + timedelta(days=39))  # Ascension
    holidays.add(easter + timedelta(days=50))  # Lundi de Pentecôte

    return holidays


def count_working_days(year: int, month: int) -> int:
    """
    Compte les jours ouvrés (Lun-Sam) du mois, hors jours fériés.
    """
    holidays = french_holidays(year)
    _, last_day = calendar.monthrange(year, month)
    count = 0
    for day in range(1, last_day + 1):
        d = date(year, month, day)
        # Lundi=0, ..., Samedi=5, Dimanche=6
        if d.weekday() <= 5 and d not in holidays:
            count += 1
    return count


def _iso_week_number(d: date) -> int:
    """Retourne le numéro de semaine ISO."""
    return d.isocalendar()[1]


def format_week_str(monday: date, sunday: date) -> str:
    """
    Retourne une chaîne comme "S12 — 16 au 22 mars" ou "S14 — 30 mars au 5 avr".
    """
    week_num = _iso_week_number(monday)
    if monday.month == sunday.month:
        # Même mois
        return f"S{week_num} — {monday.day} au {sunday.day} {FRENCH_MONTHS[sunday.month]}"
    else:
        # Mois différents
        return (
            f"S{week_num} — {monday.day} {FRENCH_MONTHS[monday.month]}"
            f" au {sunday.day} {FRENCH_MONTHS[sunday.month]}"
        )


def get_rattached_weeks(year: int, month: int):
    """
    Retourne la liste des semaines rattachées au mois.

    Une semaine est rattachée au mois où tombe son VENDREDI.

    Retourne une liste de (monday, sunday, friday, a_cheval) où :
    - a_cheval=False : vendredi dans le mois (semaines principales)
    - a_cheval=True  : lundi dans le mois mais vendredi dans le mois suivant
                       (incluses pour affichage mais exclues des totaux)
    """
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    weeks = []
    seen = set()

    # Semaines où le vendredi est dans le mois
    d = month_start
    while d <= month_end:
        if d.weekday() == 4:  # Vendredi
            friday = d
            monday = friday - timedelta(days=4)
            sunday = friday + timedelta(days=2)
            key = monday
            if key not in seen:
                seen.add(key)
                weeks.append((monday, sunday, friday, False))
        d += timedelta(days=1)

    # Semaines à cheval : lundi dans le mois, vendredi dans le mois suivant
    d = month_start
    while d <= month_end:
        if d.weekday() == 0:  # Lundi
            monday = d
            friday = monday + timedelta(days=4)
            sunday = monday + timedelta(days=6)
            # Vendredi hors du mois courant => a_cheval
            if friday > month_end and monday not in seen:
                seen.add(monday)
                weeks.append((monday, sunday, friday, True))
        d += timedelta(days=1)

    # Trier par lundi
    weeks.sort(key=lambda x: x[0])
    return weeks


def get_all_weeks_up_to(from_date: date, to_date: date):
    """
    Retourne toutes les semaines où le vendredi est dans [from_date, to_date].
    Retourne une liste de (monday, sunday, friday).
    """
    weeks = []
    seen = set()
    d = from_date
    # Chercher le premier vendredi >= from_date
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
    """Calcule le chevauchement en heures entre deux intervalles."""
    overlap_start = max(start_dt, window_start)
    overlap_end = min(end_dt, window_end)
    if overlap_end > overlap_start:
        return (overlap_end - overlap_start).total_seconds() / 3600
    return 0.0


def hours_in_plage(start_dt: datetime, end_dt: datetime, plage_ranges: list) -> float:
    """
    Calcule le total d'heures du shift tombant dans les plages horaires données.
    plage_ranges est une liste de (h_start, h_end) en heures entières (0-23).
    Si h_start > h_end, la plage est cross-midnight.
    Itère jour par jour.
    """
    if end_dt <= start_dt:
        return 0.0

    total = 0.0

    # Itérer jour par jour du début à la fin du shift
    current_day = start_dt.date()
    end_day = end_dt.date()

    while current_day <= end_day:
        for (h_start, h_end) in plage_ranges:
            if h_start <= h_end:
                # Plage normale (ex: 5h-8h ou 20h-22h)
                window_start = datetime(current_day.year, current_day.month, current_day.day, h_start, 0)
                window_end = datetime(current_day.year, current_day.month, current_day.day, h_end, 0)
                total += hours_overlap(start_dt, end_dt, window_start, window_end)
            else:
                # Plage cross-midnight (ex: 22h-5h)
                # Partie 1 : h_start → minuit
                window_start = datetime(current_day.year, current_day.month, current_day.day, h_start, 0)
                window_end = datetime(current_day.year, current_day.month, current_day.day, 23, 59, 59, 999999)
                window_end = datetime(current_day.year, current_day.month, current_day.day) + timedelta(days=1)
                total += hours_overlap(start_dt, end_dt, window_start, window_end)

                # Partie 2 : minuit → h_end (du jour suivant)
                next_day = current_day + timedelta(days=1)
                window_start2 = datetime(next_day.year, next_day.month, next_day.day, 0, 0)
                window_end2 = datetime(next_day.year, next_day.month, next_day.day, h_end, 0)
                total += hours_overlap(start_dt, end_dt, window_start2, window_end2)

        current_day += timedelta(days=1)

    return total


def sunday_hours(start_dt: datetime, end_dt: datetime) -> float:
    """Calcule les heures du shift tombant un dimanche (weekday==6)."""
    if end_dt <= start_dt:
        return 0.0

    total = 0.0
    current_day = start_dt.date()
    end_day = end_dt.date()

    while current_day <= end_day:
        if current_day.weekday() == 6:  # Dimanche
            day_start = datetime(current_day.year, current_day.month, current_day.day, 0, 0)
            day_end = day_start + timedelta(days=1)
            total += hours_overlap(start_dt, end_dt, day_start, day_end)
        current_day += timedelta(days=1)

    return total


def shift_duration_hours(shift: Shift) -> float:
    """Durée d'un shift en heures."""
    if shift.end_datetime <= shift.start_datetime:
        return 0.0
    return (shift.end_datetime - shift.start_datetime).total_seconds() / 3600


def count_working_days_in_range(start: date, end: date) -> int:
    """Compte les jours ouvrés (Lun-Sam) dans [start, end], hors fériés."""
    if end < start:
        return 0
    # Collect holidays for years spanned
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

    Args:
        pharmacy: l'objet User (pharmacie)
        year: année
        month: mois (1-12)

    Returns:
        dict avec jours_ouvres_mois, collaborateurs, totaux_salaries
    """
    _, last_day = calendar.monthrange(year, month)
    month_start = date(year, month, 1)
    month_end = date(year, month, last_day)

    jours_ouvres_mois = count_working_days(year, month)

    # Semaines rattachées : incluant celles à cheval
    rattached_weeks_all = get_rattached_weeks(year, month)
    # Semaines principales (non à cheval) pour les calculs de totaux
    rattached_weeks_main = [(m, s, f) for m, s, f, ac in rattached_weeks_all if not ac]

    # Plage de dates couverte par les semaines rattachées principales
    if rattached_weeks_main:
        range_start = rattached_weeks_main[0][0]   # premier lundi
        range_end = rattached_weeks_main[-1][1]     # dernier dimanche
    else:
        range_start = month_start
        range_end = month_end

    # Plage incluant les semaines à cheval (pour requêtes de shifts)
    if rattached_weeks_all:
        full_range_start = rattached_weeks_all[0][0]
        full_range_end = rattached_weeks_all[-1][1]
    else:
        full_range_start = month_start
        full_range_end = month_end

    # Nombre de semaines principales (pour heures_contrat)
    nb_weeks_main = len(rattached_weeks_main)

    collaborators = Collaborator.objects.filter(
        pharmacy=pharmacy,
        is_active=True
    ).order_by('display_order', 'id')

    # Shifts publiés, non absents, dans la plage complète
    all_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=full_range_start,
        start_datetime__date__lte=full_range_end,
    ).select_related('collaborator')

    # Absences sur le mois civil (pour heures nuit, dimanche, etc.)
    all_month_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=month_start,
        start_datetime__date__lte=month_end,
    ).select_related('collaborator')

    # Absence requests du mois civil (approuvées)
    all_absences = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        status='approved',
        start_date__lte=month_end,
        end_date__gte=month_start,
    ).select_related('collaborator')

    # Ajustements du mois civil
    all_adjustments = TimeAdjustment.objects.filter(
        collaborator__pharmacy=pharmacy,
        date__gte=month_start,
        date__lte=month_end,
    ).select_related('collaborator')

    # Toutes les semaines depuis le 1er janvier jusqu'à fin du mois (pour RCR annuel)
    jan_1 = date(year, 1, 1)
    annual_weeks = get_all_weeks_up_to(jan_1, month_end)

    # Shifts sur l'année jusqu'au mois (pour RCR annuel)
    all_annual_shifts = Shift.objects.filter(
        collaborator__pharmacy=pharmacy,
        is_published=True,
        is_absent=False,
        start_datetime__date__gte=jan_1,
        start_datetime__date__lte=month_end,
    ).select_related('collaborator')

    # RCR absences sur l'année jusqu'au mois
    all_annual_rcr = AbsenceRequest.objects.filter(
        collaborator__pharmacy=pharmacy,
        status='approved',
        type='rcr',
        start_date__lte=month_end,
        end_date__gte=jan_1,
    ).select_related('collaborator')

    # Indexer par collaborateur pour performance
    shifts_by_collab = {}
    for shift in all_shifts:
        if shift.collaborator_id not in shifts_by_collab:
            shifts_by_collab[shift.collaborator_id] = []
        shifts_by_collab[shift.collaborator_id].append(shift)

    month_shifts_by_collab = {}
    for shift in all_month_shifts:
        if shift.collaborator_id not in month_shifts_by_collab:
            month_shifts_by_collab[shift.collaborator_id] = []
        month_shifts_by_collab[shift.collaborator_id].append(shift)

    absences_by_collab = {}
    for absence in all_absences:
        if absence.collaborator_id not in absences_by_collab:
            absences_by_collab[absence.collaborator_id] = []
        absences_by_collab[absence.collaborator_id].append(absence)

    adjustments_by_collab = {}
    for adj in all_adjustments:
        if adj.collaborator_id not in adjustments_by_collab:
            adjustments_by_collab[adj.collaborator_id] = []
        adjustments_by_collab[adj.collaborator_id].append(adj)

    annual_shifts_by_collab = {}
    for shift in all_annual_shifts:
        if shift.collaborator_id not in annual_shifts_by_collab:
            annual_shifts_by_collab[shift.collaborator_id] = []
        annual_shifts_by_collab[shift.collaborator_id].append(shift)

    annual_rcr_by_collab = {}
    for absence in all_annual_rcr:
        if absence.collaborator_id not in annual_rcr_by_collab:
            absence.collaborator_id not in annual_rcr_by_collab
            annual_rcr_by_collab[absence.collaborator_id] = []
        annual_rcr_by_collab[absence.collaborator_id].append(absence)

    collaborateurs_data = []

    # Totaux pour salariés (non-TNS)
    totaux_jours = 0
    totaux_heures_reelles = 0.0
    totaux_heures_sup_total = 0.0
    totaux_solde_ajustements = 0.0
    totaux_nuit_20 = 0.0
    totaux_nuit_40 = 0.0
    totaux_dimanche = 0.0
    totaux_formation = 0.0
    totaux_abs_just = 0
    totaux_abs_injust = 0
    totaux_cp = 0

    for collab in collaborators:
        is_tns = getattr(collab, 'is_tns', False)
        weekly_hours = float(collab.weekly_hours)

        bg_hex, text_hex = get_collaborator_color(collab.color)

        # Initiales
        initiales = (collab.first_name[:1] + collab.last_name[:1]).upper()
        nom = f"{collab.first_name} {collab.last_name}"

        # Shifts de ce collaborateur dans la plage rattachée
        collab_shifts = shifts_by_collab.get(collab.id, [])
        collab_month_shifts = month_shifts_by_collab.get(collab.id, [])
        collab_absences = absences_by_collab.get(collab.id, [])
        collab_adjustments = adjustments_by_collab.get(collab.id, [])

        # Absences Formation du mois (approuvées)
        formation_absences = [
            a for a in collab_absences
            if a.type == 'formation'
        ]

        # Jours de formation (Lun-Sam) dans la plage rattachée (range_start .. range_end)
        formation_dates = set()
        for fa in formation_absences:
            fa_start = max(fa.start_date, range_start)
            fa_end = min(fa.end_date, range_end)
            d = fa_start
            while d <= fa_end:
                if d.weekday() <= 5:  # Lun-Sam
                    formation_dates.add(d)
                d += timedelta(days=1)

        # Heures formation (7h/jour)
        heures_formation = len(formation_dates) * 7.0

        # Jours travaillés : dates distinctes avec shifts dans rattached range + jours formation
        worked_dates = set()
        for shift in collab_shifts:
            shift_date = shift.start_datetime.date()
            if range_start <= shift_date <= range_end:
                worked_dates.add(shift_date)
        # Ajouter les jours de formation (assimilés à travail effectif)
        worked_dates_with_formation = worked_dates | formation_dates
        jours_travailles = len(worked_dates_with_formation)

        # Heures réelles : durée shifts dans plage rattachée + heures formation
        heures_reelles = sum(shift_duration_hours(s) for s in collab_shifts
                             if range_start <= s.start_datetime.date() <= range_end)
        heures_reelles += heures_formation

        if is_tns:
            # Pour les TNS : uniquement les métriques basiques
            collab_data = {
                'id': collab.id,
                'nom': nom,
                'initiales': initiales,
                'role': collab.get_role_display(),
                'is_tns': True,
                'couleur': bg_hex,
                'couleur_texte': text_hex,
                'weekly_hours': weekly_hours,
                'jours_travailles': jours_travailles,
                'heures_reelles': round(heures_reelles, 2),
                'heures_contrat': None,
                'heures_sup_planning': None,
                'detail_semaines': None,
                'solde_ajustements': None,
                'heures_nuit_20': None,
                'heures_nuit_40': None,
                'heures_dimanche': None,
                'heures_formation': round(heures_formation, 2),
                'absences_justifiees': None,
                'absences_injustifiees': None,
                'cp_poses': None,
                'annuel': None,
            }
            collaborateurs_data.append(collab_data)
            continue

        # ── Salariés ──────────────────────────────────────────────────────────

        # Heures contrat (semaines principales uniquement)
        heures_contrat = weekly_hours * nb_weeks_main

        # Détail semaines (incluant a_cheval)
        detail_semaines = []
        total_sup_tr1 = 0.0
        total_sup_tr2 = 0.0
        total_sup_total = 0.0

        for (monday, sunday, friday, a_cheval) in rattached_weeks_all:
            week_start_dt = datetime(monday.year, monday.month, monday.day, 0, 0)
            week_end_dt = datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59)

            # Heures shift dans cette semaine
            week_shift_hours = sum(
                shift_duration_hours(s)
                for s in collab_shifts
                if monday <= s.start_datetime.date() <= sunday
            )

            # Heures formation dans cette semaine
            week_formation_hours = sum(
                7.0 for fd in formation_dates if monday <= fd <= sunday
            )

            week_h = week_shift_hours + week_formation_hours

            # Heures sup de la semaine
            sup = max(0.0, week_h - weekly_hours)
            tr1 = min(sup, 8.0)
            tr2 = max(0.0, sup - 8.0)

            week_str = format_week_str(monday, sunday)
            rattachement = f"{FRENCH_MONTHS_FULL[friday.month]} {friday.year}"

            detail_semaines.append({
                'week_str': week_str,
                'heures_travaillees': round(week_h, 2),
                'seuil': weekly_hours,
                'sup_tranche1': round(tr1, 2),
                'sup_tranche2': round(tr2, 2),
                'rattachement': rattachement,
                'a_cheval': a_cheval,
            })

            # N'accumuler que les semaines non à cheval
            if not a_cheval:
                total_sup_tr1 += tr1
                total_sup_tr2 += tr2
                total_sup_total += sup

        heures_sup_planning = {
            'total': round(total_sup_total, 2),
            'tranche1': round(total_sup_tr1, 2),
            'tranche2': round(total_sup_tr2, 2),
        }

        # Solde ajustements du mois civil (heures sup - départs anticipés)
        solde_ajust = 0.0
        for adj in collab_adjustments:
            minutes = adj.duration_minutes
            if adj.type == 'overtime':
                solde_ajust += minutes / 60.0
            elif adj.type == 'early_departure':
                solde_ajust -= minutes / 60.0

        # Heures de nuit (mois civil)
        # CCN Pharmacie : +20% entre 20h-22h et 5h-8h
        heures_nuit_20 = 0.0
        # CCN Pharmacie : +40% entre 22h-5h (cross-midnight)
        heures_nuit_40 = 0.0

        plage_20 = [(20, 22), (5, 8)]  # plages +20%
        plage_40 = [(22, 5)]           # plage +40% (cross-midnight)

        for shift in collab_month_shifts:
            start_dt = shift.start_datetime
            end_dt = shift.end_datetime
            if not isinstance(start_dt, datetime):
                start_dt = datetime.combine(start_dt, datetime.min.time())
            if not isinstance(end_dt, datetime):
                end_dt = datetime.combine(end_dt, datetime.min.time())
            heures_nuit_20 += hours_in_plage(start_dt, end_dt, plage_20)
            heures_nuit_40 += hours_in_plage(start_dt, end_dt, plage_40)

        # Heures dimanche (mois civil)
        heures_dimanche = 0.0
        for shift in collab_month_shifts:
            start_dt = shift.start_datetime
            end_dt = shift.end_datetime
            if not isinstance(start_dt, datetime):
                start_dt = datetime.combine(start_dt, datetime.min.time())
            if not isinstance(end_dt, datetime):
                end_dt = datetime.combine(end_dt, datetime.min.time())
            heures_dimanche += sunday_hours(start_dt, end_dt)

        # Absences mois civil (jours ouvrés)
        abs_just = 0
        abs_injust = 0
        cp_poses = 0

        for absence in collab_absences:
            # Intersecter avec le mois civil
            abs_start = max(absence.start_date, month_start)
            abs_end = min(absence.end_date, month_end)
            n_days = count_working_days_in_range(abs_start, abs_end)

            if absence.type == 'injustifiee':
                abs_injust += n_days
            elif absence.type in ('justifiee', 'maladie', 'rcr', 'sans_solde', 'formation'):
                abs_just += n_days
            elif absence.type == 'cp':
                cp_poses += n_days

        # ── Calcul annuel RCR ──────────────────────────────────────────────────

        collab_annual_shifts = annual_shifts_by_collab.get(collab.id, [])
        collab_annual_rcr = annual_rcr_by_collab.get(collab.id, [])

        # Heures sup accumulées depuis Jan 1 jusqu'à la fin du mois
        rcr_acquis_h = 0.0
        for (w_monday, w_sunday, w_friday) in annual_weeks:
            week_shift_h = sum(
                shift_duration_hours(s)
                for s in collab_annual_shifts
                if w_monday <= s.start_datetime.date() <= w_sunday
            )
            # Formation dans cette semaine annuelle
            week_form_h = 0.0
            for fa in [a for a in AbsenceRequest.objects.filter(
                collaborator=collab,
                type='formation',
                status='approved',
                start_date__lte=w_sunday,
                end_date__gte=w_monday,
            )]:
                fa_start = max(fa.start_date, w_monday)
                fa_end = min(fa.end_date, w_sunday)
                d = fa_start
                while d <= fa_end:
                    if d.weekday() <= 5:
                        week_form_h += 7.0
                    d += timedelta(days=1)

            week_total_h = week_shift_h + week_form_h
            week_sup = max(0.0, week_total_h - weekly_hours)
            rcr_acquis_h += week_sup

        # RCR consommé : absences RCR approuvées (en jours ouvrés * 7h)
        rcr_consomme_h = 0.0
        for absence in collab_annual_rcr:
            rcr_start = max(absence.start_date, jan_1)
            rcr_end = min(absence.end_date, month_end)
            n_days = count_working_days_in_range(rcr_start, rcr_end)
            rcr_consomme_h += n_days * 7.0

        rcr_solde_h = rcr_acquis_h - rcr_consomme_h
        rcr_alerte = rcr_solde_h > 150.0  # Contingent réglementaire CCN

        # Contingent annuel d'heures sup consommé (en heures)
        contingent_consomme = rcr_acquis_h

        annuel = {
            'rcr_acquis': round(rcr_acquis_h, 2),
            'rcr_consomme': round(rcr_consomme_h, 2),
            'rcr_solde': round(rcr_solde_h, 2),
            'rcr_alerte': rcr_alerte,
            'contingent_consomme': round(contingent_consomme, 2),
        }

        collab_data = {
            'id': collab.id,
            'nom': nom,
            'initiales': initiales,
            'role': collab.get_role_display(),
            'is_tns': False,
            'couleur': bg_hex,
            'couleur_texte': text_hex,
            'weekly_hours': weekly_hours,
            'jours_travailles': jours_travailles,
            'heures_reelles': round(heures_reelles, 2),
            'heures_contrat': round(heures_contrat, 2),
            'heures_sup_planning': heures_sup_planning,
            'detail_semaines': detail_semaines,
            'solde_ajustements': round(solde_ajust, 2),
            'heures_nuit_20': round(heures_nuit_20, 2),
            'heures_nuit_40': round(heures_nuit_40, 2),
            'heures_dimanche': round(heures_dimanche, 2),
            'heures_formation': round(heures_formation, 2),
            'absences_justifiees': abs_just,
            'absences_injustifiees': abs_injust,
            'cp_poses': cp_poses,
            'annuel': annuel,
        }
        collaborateurs_data.append(collab_data)

        # Agréger dans les totaux salariés
        totaux_jours += jours_travailles
        totaux_heures_reelles += heures_reelles
        totaux_heures_sup_total += total_sup_total
        totaux_solde_ajustements += solde_ajust
        totaux_nuit_20 += heures_nuit_20
        totaux_nuit_40 += heures_nuit_40
        totaux_dimanche += heures_dimanche
        totaux_formation += heures_formation
        totaux_abs_just += abs_just
        totaux_abs_injust += abs_injust
        totaux_cp += cp_poses

    totaux_salaries = {
        'jours_travailles': totaux_jours,
        'heures_reelles': round(totaux_heures_reelles, 2),
        'heures_sup_planning_total': round(totaux_heures_sup_total, 2),
        'solde_ajustements': round(totaux_solde_ajustements, 2),
        'heures_nuit_20': round(totaux_nuit_20, 2),
        'heures_nuit_40': round(totaux_nuit_40, 2),
        'heures_dimanche': round(totaux_dimanche, 2),
        'heures_formation': round(totaux_formation, 2),
        'absences_justifiees': totaux_abs_just,
        'absences_injustifiees': totaux_abs_injust,
        'cp_poses': totaux_cp,
    }

    return {
        'month': f"{year}-{month:02d}",
        'jours_ouvres_mois': jours_ouvres_mois,
        'collaborateurs': collaborateurs_data,
        'totaux_salaries': totaux_salaries,
    }
