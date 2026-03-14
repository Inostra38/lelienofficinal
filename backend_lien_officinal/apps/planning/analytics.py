"""
PlanningAnalytics — calculs statistiques pour la vue analytique du planning.
"""
from datetime import date, timedelta
import calendar as cal_module


class PlanningAnalytics:
    """
    Classe utilitaire pour calculer les métriques analytiques du planning
    d'une pharmacie sur une période donnée.
    """

    def __init__(self, pharmacy):
        self.pharmacy = pharmacy

    # ── Heures travaillées vs contrat ─────────────────────────────────────────

    def hours_summary(self, date_from: date, date_to: date) -> list:
        """
        Retourne par collaborateur actif :
          - total_hours    : heures planifiées (shifts publiés)
          - contract_hours : heures contractuelles sur la période
          - extra_hours    : écart (total - contrat)
          - presence_days  : nombre de jours où au moins 1 shift est présent
        """
        from apps.team.models import Collaborator
        from .models import Shift

        nb_days  = (date_to - date_from).days + 1
        nb_weeks = nb_days / 7.0

        collaborators = Collaborator.objects.filter(
            pharmacy=self.pharmacy,
            is_active=True,
        ).order_by('display_order', 'id')

        result = []
        for collab in collaborators:
            shifts = Shift.objects.filter(
                collaborator=collab,
                is_published=True,
                start_datetime__date__gte=date_from,
                start_datetime__date__lte=date_to,
            )

            total_hours   = sum(
                (s.end_datetime - s.start_datetime).total_seconds() / 3600
                for s in shifts
            )
            presence_days = shifts.dates('start_datetime', 'day').count()
            contract_h    = float(collab.weekly_hours) * nb_weeks
            extra_h       = total_hours - contract_h

            result.append({
                'collaborator_id':   collab.id,
                'collaborator_name': f"{collab.first_name} {collab.last_name}",
                'role':              collab.get_role_display(),
                'total_hours':       round(total_hours, 2),
                'contract_hours':    round(contract_h,  2),
                'extra_hours':       round(extra_h,     2),
                'presence_days':     presence_days,
            })

        return result

    # ── Absences ──────────────────────────────────────────────────────────────

    def absences_summary(self, date_from: date, date_to: date) -> dict:
        """
        Retourne :
          - by_type         : { cp, maladie, rcr, sans_solde } en nombre de jours
          - by_collaborator : { "Prénom Nom": { cp, maladie, rcr, sans_solde } }
        Seules les absences approuvées sont comptabilisées.
        """
        from .models import AbsenceRequest

        absences = AbsenceRequest.objects.filter(
            collaborator__pharmacy=self.pharmacy,
            collaborator__is_active=True,
            status=AbsenceRequest.Status.APPROVED,
            start_date__lte=date_to,
            end_date__gte=date_from,
        ).select_related('collaborator')

        by_type = {'cp': 0, 'maladie': 0, 'rcr': 0, 'sans_solde': 0}
        by_collab: dict = {}

        for absence in absences:
            # Intersection avec la période demandée
            eff_start = max(absence.start_date, date_from)
            eff_end   = min(absence.end_date,   date_to)
            nb_days   = (eff_end - eff_start).days + 1

            abs_type = absence.type  # 'cp' | 'maladie' | 'rcr' | 'sans_solde'
            if abs_type in by_type:
                by_type[abs_type] += nb_days

            name = f"{absence.collaborator.first_name} {absence.collaborator.last_name}"
            if name not in by_collab:
                by_collab[name] = {'cp': 0, 'maladie': 0, 'rcr': 0, 'sans_solde': 0}
            if abs_type in by_collab[name]:
                by_collab[name][abs_type] += nb_days

        return {
            'by_type':         by_type,
            'by_collaborator': by_collab,
        }

    # ── Solde CP ──────────────────────────────────────────────────────────────

    def cp_balance(self, date_from: date, date_to: date) -> list:
        """
        Calcule par collaborateur :
          - cp_acquired : CP acquis sur la période (approximation : 2.5j / mois)
          - cp_used     : CP posés (approuvés) sur la période
          - cp_balance  : cp_acquired - cp_used
        """
        from apps.team.models import Collaborator
        from .models import AbsenceRequest

        # Nombre de mois (approximatif) sur la période
        nb_days   = (date_to - date_from).days + 1
        nb_months = nb_days / 30.44

        collaborators = Collaborator.objects.filter(
            pharmacy=self.pharmacy,
            is_active=True,
        ).order_by('display_order', 'id')

        result = []
        for collab in collaborators:
            cp_used_days = 0
            cp_absences  = AbsenceRequest.objects.filter(
                collaborator=collab,
                type=AbsenceRequest.AbsenceType.CP,
                status=AbsenceRequest.Status.APPROVED,
                start_date__lte=date_to,
                end_date__gte=date_from,
            )
            for absence in cp_absences:
                eff_start     = max(absence.start_date, date_from)
                eff_end       = min(absence.end_date,   date_to)
                cp_used_days += (eff_end - eff_start).days + 1

            cp_acquired = round(2.5 * nb_months, 1)
            cp_balance  = round(cp_acquired - cp_used_days, 1)

            result.append({
                'collaborator_name': f"{collab.first_name} {collab.last_name}",
                'cp_acquired':       cp_acquired,
                'cp_used':           cp_used_days,
                'cp_balance':        cp_balance,
            })

        return result

    # ── Taux de couverture ────────────────────────────────────────────────────

    def coverage_rate(self, date_from: date, date_to: date):
        """
        Compare les heures d'ouverture théoriques (OpeningHours) avec les
        heures de shifts publiés sur la période.

        Retourne None si aucun horaire d'ouverture n'est défini.
        """
        from .models import OpeningHours, PharmacyDayStatus, Shift

        opening_slots = OpeningHours.objects.filter(pharmacy=self.pharmacy)
        if not opening_slots.exists():
            return None

        # Construire un dict day_of_week → total heures journalières théoriques
        hours_by_dow: dict[int, float] = {}
        for slot in opening_slots:
            h_start = slot.start_time.hour + slot.start_time.minute / 60.0
            h_end   = slot.end_time.hour   + slot.end_time.minute   / 60.0
            duration = h_end - h_start
            if duration > 0:
                hours_by_dow[slot.day_of_week] = hours_by_dow.get(slot.day_of_week, 0) + duration

        # Récupérer les jours fermés sur la période
        closed_dates = set(
            PharmacyDayStatus.objects.filter(
                pharmacy=self.pharmacy,
                date__gte=date_from,
                date__lte=date_to,
                status=PharmacyDayStatus.Status.CLOSED,
            ).values_list('date', flat=True)
        )

        theoretical_hours = 0.0
        current = date_from
        while current <= date_to:
            dow = current.weekday()  # 0=Lundi … 6=Dimanche
            if current not in closed_dates and dow in hours_by_dow:
                theoretical_hours += hours_by_dow[dow]
            current += timedelta(days=1)

        # Heures réelles : shifts publiés
        shifts = Shift.objects.filter(
            collaborator__pharmacy=self.pharmacy,
            is_published=True,
            start_datetime__date__gte=date_from,
            start_datetime__date__lte=date_to,
        )
        actual_hours = sum(
            (s.end_datetime - s.start_datetime).total_seconds() / 3600
            for s in shifts
        )

        coverage_rate = (
            round(actual_hours / theoretical_hours * 100, 1)
            if theoretical_hours > 0 else 0.0
        )

        return {
            'theoretical_hours': round(theoretical_hours, 2),
            'actual_hours':       round(actual_hours,      2),
            'coverage_rate':      coverage_rate,
        }

    # ── Gardes ────────────────────────────────────────────────────────────────

    def on_call_summary(self, date_from: date, date_to: date) -> dict:
        """
        Compte les jours de garde de jour / nuit sur la période via PharmacyDayStatus.
        """
        from .models import PharmacyDayStatus

        qs = PharmacyDayStatus.objects.filter(
            pharmacy=self.pharmacy,
            date__gte=date_from,
            date__lte=date_to,
        )

        day_guards   = qs.filter(on_call_day=True).count()
        night_guards = qs.filter(on_call_night=True).count()

        return {
            'day_guards':   day_guards,
            'night_guards': night_guards,
            'total':        day_guards + night_guards,
        }

    # ── Évolution mensuelle ───────────────────────────────────────────────────

    def monthly_evolution(self, year: int) -> list:
        """
        Retourne pour chaque mois de l'année :
          - month       : numéro (1-12)
          - month_label : libellé court en français
          - total_hours : heures de shifts publiés
          - absences    : nombre de jours d'absence approuvés
        """
        from .models import Shift, AbsenceRequest

        MONTH_LABELS = [
            '', 'Jan', 'Fév', 'Mar', 'Avr', 'Mai', 'Juin',
            'Juil', 'Août', 'Sep', 'Oct', 'Nov', 'Déc',
        ]

        result = []
        for month in range(1, 13):
            first_day = date(year, month, 1)
            last_day  = date(year, month, cal_module.monthrange(year, month)[1])

            shifts = Shift.objects.filter(
                collaborator__pharmacy=self.pharmacy,
                is_published=True,
                start_datetime__date__gte=first_day,
                start_datetime__date__lte=last_day,
            )
            total_hours = sum(
                (s.end_datetime - s.start_datetime).total_seconds() / 3600
                for s in shifts
            )

            absences = AbsenceRequest.objects.filter(
                collaborator__pharmacy=self.pharmacy,
                collaborator__is_active=True,
                status=AbsenceRequest.Status.APPROVED,
                start_date__lte=last_day,
                end_date__gte=first_day,
            )
            absence_days = 0
            for absence in absences:
                eff_start     = max(absence.start_date, first_day)
                eff_end       = min(absence.end_date,   last_day)
                absence_days += (eff_end - eff_start).days + 1

            result.append({
                'month':       month,
                'month_label': MONTH_LABELS[month],
                'total_hours': round(total_hours, 1),
                'absences':    absence_days,
            })

        return result
