"""
Management command : peuplement des données planning pour le développement.

Usage :
    python manage.py seed_planning [--from 2026-04-05] [--to 2026-06-30]

Crée des shifts réalistes pour la Pharmacie du Centre (centre@test.com) :
  - Sophie Martin  (TNS, 17h/semaine) : mi-temps, surtout matin
  - Marc Dupont    (35h/semaine)      : plein temps, adjoint
  - Julie Bernard  (32h/semaine)      : préparatrice
  - Thomas Leroy   (20h/semaine)      : étudiant, quelques demi-journées

Idempotent sur la période : efface les shifts existants sur la plage
puis les recrée.
"""
import random
from datetime import date, datetime, timedelta, time
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from apps.planning.models import (
    Shift, TimeAdjustment, AbsenceRequest, PharmacyDayStatus,
)

TZ = ZoneInfo("Europe/Paris")
SEED = 42


def make_dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)


def jours_feries_2026():
    """Jours fériés 2026 (Meeus/Jones/Butcher)."""
    year = 2026
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    ii, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * ii - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    e_month = (h + l - 7 * m + 114) // 31
    e_day   = (h + l - 7 * m + 114) % 31 + 1
    paques  = date(year, e_month, e_day)

    def s(n): return paques + timedelta(n)

    return {
        date(2026,  1,  1), s(1),
        date(2026,  5,  1), date(2026, 5, 8),
        s(39), s(50),
        date(2026,  7, 14), date(2026, 8, 15),
        date(2026, 11,  1), date(2026, 11, 11),
        date(2026, 12, 25),
    }


FERIES = jours_feries_2026()


class Command(BaseCommand):
    help = "Peuple les données planning (shifts, absences, ajustements) Jan–Juin 2026"

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="date_from", default="2026-04-05")
        parser.add_argument("--to",   dest="date_to",   default="2026-06-30")

    def handle(self, *args, **options):
        random.seed(SEED)
        date_from = date.fromisoformat(options["date_from"])
        date_to   = date.fromisoformat(options["date_to"])

        pharmacy = Pharmacy.objects.get(email="centre@test.com")
        collabs  = {
            c.first_name: c
            for c in Collaborator.objects.filter(pharmacy=pharmacy, is_active=True)
        }
        sophie = collabs["Sophie"]
        marc   = collabs["Marc"]
        julie  = collabs["Julie"]
        thomas = collabs["Thomas"]

        with transaction.atomic():
            # Efface la plage
            Shift.objects.filter(
                collaborator__pharmacy=pharmacy,
                start_datetime__date__gte=date_from,
                start_datetime__date__lte=date_to,
                is_published=True,
            ).delete()
            TimeAdjustment.objects.filter(
                collaborator__pharmacy=pharmacy,
                date__gte=date_from,
                date__lte=date_to,
            ).delete()
            AbsenceRequest.objects.filter(
                collaborator__pharmacy=pharmacy,
                start_date__gte=date_from,
                start_date__lte=date_to,
            ).delete()
            PharmacyDayStatus.objects.filter(
                pharmacy=pharmacy,
                date__gte=date_from,
                date__lte=date_to,
            ).delete()

            self._seed_shifts(pharmacy, sophie, marc, julie, thomas, date_from, date_to)
            self._seed_absences(pharmacy, marc, julie, thomas, date_from, date_to)
            self._seed_adjustments(pharmacy, marc, julie, thomas, date_from, date_to)
            self._seed_day_statuses(pharmacy, date_from, date_to)
            self._seed_sunday_gardes(pharmacy, marc, julie, date_from, date_to)

        self.stdout.write(self.style.SUCCESS(
            f"\n✅ Planning peuplé du {date_from} au {date_to}\n"
        ))

    # ── Shifts ──────────────────────────────────────────────────────────────────

    def _seed_shifts(self, pharmacy, sophie, marc, julie, thomas, d_from, d_to):
        """
        Génère les shifts semaine par semaine.
        Patrons :
          Sophie (TNS 17h) : L/M/J matin 9h–12h30 + 1 après-midi/semaine
          Marc   (35h)     : L-S alterné matin/après-midi
          Julie  (32h)     : L-V + 1 sam/2
          Thomas (20h)     : 4 demi-journées + 1 samedi
        """
        # Congés planifiés (périodes à ne pas shifter)
        absences = self._absence_periods()

        cur = d_from
        week_idx = 0
        shifts_batch = []

        while cur <= d_to:
            # Début de semaine (lundi)
            monday = cur - timedelta(days=cur.weekday())
            if monday < d_from:
                monday = d_from
            sunday = monday + timedelta(6)

            week_shifts = self._week_shifts(
                monday, sunday, sophie, marc, julie, thomas, absences, week_idx
            )
            shifts_batch.extend(week_shifts)

            cur = monday + timedelta(7)
            week_idx += 1

        Shift.objects.bulk_create(shifts_batch)
        self.stdout.write(f"  📅 {len(shifts_batch)} shifts créés")

    def _absence_periods(self):
        """Périodes de congés/absences planifiées (dict collab → liste de dates)."""
        return {
            # Marc : RCR 2 jours en mai
            "marc_rcr_mai":   (date(2026, 5, 11), date(2026, 5, 12)),
            # Julie : CP 1 semaine fin mai
            "julie_cp_mai":   (date(2026, 5, 25), date(2026, 5, 29)),
            # Thomas : CP 2 semaines en juin
            "thomas_cp_juin": (date(2026, 6, 8),  date(2026, 6, 19)),
            # Marc : CP 1 semaine en juin
            "marc_cp_juin":   (date(2026, 6, 22), date(2026, 6, 26)),
            # Sophie : 1 semaine congé juillet avancé en juin — pas dans la plage
        }

    def _is_off(self, d: date, collab_key: str, absences: dict) -> bool:
        for key, (start, end) in absences.items():
            if key.startswith(collab_key) and start <= d <= end:
                return True
        return False

    def _week_shifts(self, monday, sunday, sophie, marc, julie, thomas, absences, week_idx):
        shifts = []
        marc_late_week = (week_idx % 2 == 0)  # alternance matin/après-midi semaines paires

        for day_offset in range(7):
            d = monday + timedelta(day_offset)
            if d > sunday or d > date(2026, 6, 30):
                continue
            wd = d.weekday()  # 0=lundi ... 6=dimanche
            is_sunday = wd == 6
            is_saturday = wd == 5
            is_ferie = d in FERIES

            if is_sunday:
                continue  # pharmacie fermée

            # ── Sophie (TNS 17h) : L/M/J + 1 AM/semaine
            if not is_ferie and not self._is_off(d, "sophie", absences):
                if wd in (0, 1, 3):  # Lun, Mar, Jeu
                    shifts.append(self._s(sophie, d, 9, 0, 12, 30))
                elif wd == 4 and week_idx % 3 == 0:  # Vendredi 1 sem/3
                    shifts.append(self._s(sophie, d, 14, 0, 17, 30))

            # ── Marc (35h) : L-S, alternance matin/soirée
            if not self._is_off(d, "marc", absences):
                if is_ferie and not is_saturday:
                    # Garde jour si férié en semaine (pharmacie de garde)
                    if not is_sunday:
                        shifts.append(self._s(marc, d, 9, 0, 12, 30, is_absent=False))
                elif marc_late_week:
                    # Semaines paires : matin
                    if wd <= 5:
                        shifts.append(self._s(marc, d, 9, 0, 17, 0))
                else:
                    # Semaines impaires : décalé
                    if wd <= 4:
                        shifts.append(self._s(marc, d, 11, 0, 19, 0))
                    elif is_saturday:
                        shifts.append(self._s(marc, d, 9, 0, 13, 0))

            # ── Julie (32h) : L-V + 1 sam/2
            if not is_ferie and not self._is_off(d, "julie", absences):
                if wd <= 4:  # Lun–Ven
                    # Alterne matin/après-midi
                    if (week_idx + wd) % 2 == 0:
                        shifts.append(self._s(julie, d, 9, 0, 17, 0))
                    else:
                        shifts.append(self._s(julie, d, 9, 30, 13, 0))
                        shifts.append(self._s(julie, d, 14, 0, 17, 30))
                elif is_saturday and week_idx % 2 == 0:
                    shifts.append(self._s(julie, d, 9, 0, 13, 0))

            # ── Thomas (20h) : demi-journées + sam
            if not is_ferie and not self._is_off(d, "thomas", absences):
                if wd in (1, 3) and not is_saturday:  # Mar, Jeu
                    shifts.append(self._s(thomas, d, 14, 0, 19, 0))
                elif wd == 0:  # Lundi
                    shifts.append(self._s(thomas, d, 9, 0, 13, 0))
                elif is_saturday and week_idx % 3 != 2:
                    shifts.append(self._s(thomas, d, 9, 0, 13, 0))

        return shifts

    def _s(self, collab, d: date, h_start, m_start, h_end, m_end,
           is_absent=False, absence_type=None) -> Shift:
        return Shift(
            collaborator=collab,
            collaborator_snapshot=f"{collab.first_name} {collab.last_name}",
            start_datetime=make_dt(d, h_start, m_start),
            end_datetime=make_dt(d, h_end, m_end),
            is_published=True,
            is_absent=is_absent,
            absence_type=absence_type,
            contract_hours_snapshot=collab.weekly_hours,
        )

    # ── Absences ────────────────────────────────────────────────────────────────

    def _seed_absences(self, pharmacy, marc, julie, thomas, d_from, d_to):
        records = [
            # Marc : RCR 2 jours mai
            dict(collaborator=marc, start_date=date(2026, 5, 11), end_date=date(2026, 5, 12),
                 type="rcr", status="approved"),
            # Marc : CP 1 semaine juin
            dict(collaborator=marc, start_date=date(2026, 6, 22), end_date=date(2026, 6, 26),
                 type="cp", status="approved"),
            # Julie : CP fin mai
            dict(collaborator=julie, start_date=date(2026, 5, 25), end_date=date(2026, 5, 29),
                 type="cp", status="approved"),
            # Thomas : CP 2 semaines juin
            dict(collaborator=thomas, start_date=date(2026, 6, 8), end_date=date(2026, 6, 19),
                 type="cp", status="approved"),
            # Thomas : formation DPC en avril (2 jours)
            dict(collaborator=thomas, start_date=date(2026, 4, 22), end_date=date(2026, 4, 23),
                 type="formation", status="approved"),
            # Julie : maladie 2 jours en mai
            dict(collaborator=julie, start_date=date(2026, 5, 6), end_date=date(2026, 5, 7),
                 type="maladie", status="approved"),
            # Marc : absence injustifiée 1 jour en avril
            dict(collaborator=marc, start_date=date(2026, 4, 17), end_date=date(2026, 4, 17),
                 type="injustifiee", status="approved"),
        ]

        created = 0
        for r in records:
            if r["start_date"] >= d_from and r["start_date"] <= d_to:
                _, ok = AbsenceRequest.objects.get_or_create(
                    collaborator=r["collaborator"],
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    defaults={"type": r["type"], "status": r["status"]},
                )
                if ok:
                    created += 1

        # Marquer les shifts comme absents pour absences injustifiées/maladie
        inj = AbsenceRequest.objects.filter(
            collaborator__pharmacy=pharmacy,
            type__in=["injustifiee", "maladie"],
            start_date__gte=d_from,
        )
        for abs_req in inj:
            Shift.objects.filter(
                collaborator=abs_req.collaborator,
                start_datetime__date__gte=abs_req.start_date,
                start_datetime__date__lte=abs_req.end_date,
                is_published=True,
            ).update(
                is_absent=True,
                absence_type="injustifiee" if abs_req.type == "injustifiee" else "justifiee",
            )

        self.stdout.write(f"  🏖  {created} absences créées")

    # ── Ajustements horaires ─────────────────────────────────────────────────────

    def _seed_adjustments(self, pharmacy, marc, julie, thomas, d_from, d_to):
        records = [
            # Marc : heures sup lors d'un inventaire
            dict(collab=marc, d=date(2026, 4, 10), type="overtime",
                 ref=time(17, 0), actual=time(19, 0), minutes=120,
                 note="Inventaire trimestriel"),
            # Julie : départ anticipé (enfant malade)
            dict(collab=julie, d=date(2026, 4, 16), type="early_departure",
                 ref=time(17, 30), actual=time(15, 30), minutes=120,
                 note="Enfant malade"),
            # Marc : heures sup formation interne
            dict(collab=marc, d=date(2026, 5, 14), type="overtime",
                 ref=time(17, 0), actual=time(18, 30), minutes=90,
                 note="Formation MSP"),
            # Thomas : départ anticipé
            dict(collab=thomas, d=date(2026, 4, 28), type="early_departure",
                 ref=time(19, 0), actual=time(18, 0), minutes=60,
                 note="Examen universitaire"),
            # Marc : heures sup veille férié
            dict(collab=marc, d=date(2026, 4, 30), type="overtime",
                 ref=time(17, 0), actual=time(19, 30), minutes=150,
                 note="Préparation veille 1er mai"),
            # Julie : heures sup fin de mois
            dict(collab=julie, d=date(2026, 5, 29), type="overtime",
                 ref=time(17, 30), actual=time(19, 0), minutes=90,
                 note="Clôture stock mensuel"),
            # Marc : heures sup juin
            dict(collab=marc, d=date(2026, 6, 5), type="overtime",
                 ref=time(17, 0), actual=time(19, 0), minutes=120,
                 note="Audit interne"),
            # Julie : départ anticipé juin
            dict(collab=julie, d=date(2026, 6, 19), type="early_departure",
                 ref=time(17, 30), actual=time(16, 0), minutes=90,
                 note="RDV médical"),
        ]

        created = 0
        for r in records:
            if r["d"] >= d_from and r["d"] <= d_to:
                _, ok = TimeAdjustment.objects.get_or_create(
                    collaborator=r["collab"],
                    date=r["d"],
                    type=r["type"],
                    defaults={
                        "actual_time": r["actual"],
                        "reference_time": r["ref"],
                        "duration_minutes": r["minutes"],
                        "note": r["note"],
                    },
                )
                if ok:
                    created += 1

        self.stdout.write(f"  ⏱  {created} ajustements créés")

    # ── Statuts journaliers ──────────────────────────────────────────────────────

    def _seed_day_statuses(self, pharmacy, d_from, d_to):
        """Marque les jours fériés comme fermés (sauf garde si besoin)."""
        created = 0
        cur = d_from
        while cur <= d_to:
            if cur in FERIES:
                _, ok = PharmacyDayStatus.objects.get_or_create(
                    pharmacy=pharmacy,
                    date=cur,
                    defaults={"status": "closed", "on_call_day": False, "on_call_night": False},
                )
                if ok:
                    created += 1
            cur += timedelta(1)

        self.stdout.write(f"  📆  {created} statuts jours fériés créés")

    # ── Gardes dimanche ──────────────────────────────────────────────────────────

    def _seed_sunday_gardes(self, pharmacy, marc, julie, d_from, d_to):
        """
        Quelques dimanches en garde de jour, avec shifts correspondants.
        Horaires : 9h–12h (garde légère, 3h).
        """
        GARDES = [
            # (date, collaborateur, garde_nuit?)
            (date(2026, 4, 12), marc,  False),
            (date(2026, 4, 26), marc,  True),   # garde nuit uniquement (pas de shift)
            (date(2026, 5, 17), marc,  False),
            (date(2026, 5, 31), julie, False),
            (date(2026, 6,  7), marc,  False),
            (date(2026, 6, 28), julie, False),
        ]

        shifts_created = 0
        statuts_created = 0

        for (d, collab, nuit_only) in GARDES:
            if d < d_from or d > d_to:
                continue

            on_call_day   = not nuit_only
            on_call_night = nuit_only

            _, ok = PharmacyDayStatus.objects.get_or_create(
                pharmacy=pharmacy,
                date=d,
                defaults={
                    "status": "open",
                    "on_call_day": on_call_day,
                    "on_call_night": on_call_night,
                },
            )
            if ok:
                statuts_created += 1

            # Shift uniquement pour les gardes de jour
            if on_call_day:
                _, created = Shift.objects.get_or_create(
                    collaborator=collab,
                    start_datetime=make_dt(d, 9, 0),
                    defaults={
                        "collaborator_snapshot": f"{collab.first_name} {collab.last_name}",
                        "end_datetime": make_dt(d, 12, 0),
                        "is_published": True,
                        "contract_hours_snapshot": collab.weekly_hours,
                    },
                )
                if created:
                    shifts_created += 1

        self.stdout.write(f"  🌞  {statuts_created} gardes dimanche + {shifts_created} shifts créés")
