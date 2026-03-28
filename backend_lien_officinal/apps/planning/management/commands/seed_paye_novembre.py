"""
Management command : données démo récap paie — novembre 2026.

Couvre tous les cas de figure du récap paie CCN Pharmacie :

  Marc Dupont (Adjoint, 35h)
    S45 (2-8 nov)   : Lun-Ven 9h-17h → 40h, tr1=5h
    Nov 1 Toussaint  : shift dimanche 10h-14h → jour férié travaillé + dimanche
    S46 (9-15 nov)  : Lun-Dim 9h-17h = 7j/56h → ⚠ 46h + ⚠ 6j + Nov11 Armistice + dimanche
    S47 (16-22 nov) : CP lun-ven
    S48 (23-29 nov) : Lun-Ven 9h-17h + overtime jeu +3h → 43h, tr1=8h
    S49 (30 nov)    : a_cheval lun 9h-17h

  Julie Bernard (Préparatrice, 35h)
    S45 (2-8 nov)   : Nuit Lun-Ven 20h-04h → nuit_40=30h, nuit_20=10h
    S46 (9-15 nov)  : présente lun/mer/jeu/ven + abs.injust. mar + départ anticipé jeu -2h + Nov11 travaillé
    S47 (16-22 nov) : Formation lun-ven (AbsenceRequest)
    S48 (23-29 nov) : Lun-Ven 9h-17h + dim 29 10h-14h → tr2=1h + dimanche
    S49 (30 nov)    : a_cheval lun 9h-17h

  Thomas Leroy (Étudiant, 20h)
    S45 (2-8 nov)   : Lun-Dim 9h-17h = 7j/56h → ⚠ 46h + ⚠ 6j + dimanche + tr2=28h
    S46 (9-15 nov)  : Lun+Ven 9h-20h30 (11.5h) + Mar-Jeu 9h-17h → ⚠ 46h + ⚠ 10h + tr2
    S47 (16-22 nov) : RCR lun-ven (AbsenceRequest)
    S48 (23-29 nov) : Lun-Ven 9h-17h → sup = 20h, tr2=12h
    S49 (30 nov)    : a_cheval lun 9h-17h

  Dr. Alain Morin (Pharmacien gérant, TNS — créé s'il n'existe pas)
    S45-S48         : Lun-Ven 9h-17h

Usage :
    python manage.py seed_paye_novembre
    python manage.py seed_paye_novembre --pharmacy 2   # autre pharmacie
    python manage.py seed_paye_novembre --flush        # supprime les données créées
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.core.models import Pharmacy
from apps.team.models import Collaborator
from apps.planning.models import Shift, TimeAdjustment, AbsenceRequest

TZ = ZoneInfo("Europe/Paris")

NOV = 2026

def dt(d: date, h: int, m: int = 0) -> datetime:
    return datetime(d.year, d.month, d.day, h, m, tzinfo=TZ)

def shift(collab, d: date, h_start: int, h_end: int,
          end_date: date | None = None,
          absent: bool = False, abs_type: str | None = None) -> Shift:
    end_d = end_date or d
    return Shift(
        collaborator=collab,
        collaborator_snapshot=f"{collab.first_name} {collab.last_name}",
        start_datetime=dt(d, h_start),
        end_datetime=dt(end_d, h_end, 30) if (h_end == 20 and end_date is None) else dt(end_d, h_end),
        is_published=True,
        is_absent=absent,
        absence_type=abs_type,
        contract_hours_snapshot=collab.weekly_hours,
    )


class Command(BaseCommand):
    help = "Crée les données démo récap paie pour novembre 2026 (tous les cas CCN)"

    def add_arguments(self, parser):
        parser.add_argument("--pharmacy", type=int, default=1)
        parser.add_argument("--flush", action="store_true",
                            help="Supprime uniquement les données créées par ce seed")

    def handle(self, *args, **options):
        pharmacy = Pharmacy.objects.get(pk=options["pharmacy"])
        self.stdout.write(f"Pharmacie : {pharmacy.nom_officine}")

        if options["flush"]:
            self._flush(pharmacy)
            return

        with transaction.atomic():
            self._seed(pharmacy)

    # ── Flush ──────────────────────────────────────────────────────────────────

    def _flush(self, pharmacy):
        collabs = Collaborator.objects.filter(pharmacy=pharmacy, last_name__in=[
            "Dupont", "Bernard", "Leroy", "Morin-Demo",
        ])
        # Shifts novembre + décembre début (a_cheval)
        Shift.objects.filter(
            collaborator__in=collabs,
            start_datetime__date__gte=date(2026, 11, 1),
            start_datetime__date__lte=date(2026, 12, 6),
        ).delete()
        TimeAdjustment.objects.filter(
            collaborator__in=collabs,
            date__gte=date(2026, 11, 1),
            date__lte=date(2026, 11, 30),
        ).delete()
        AbsenceRequest.objects.filter(
            collaborator__in=collabs,
            start_date__gte=date(2026, 11, 1),
            start_date__lte=date(2026, 11, 30),
        ).delete()
        # Supprimer le TNS démo uniquement
        Collaborator.objects.filter(pharmacy=pharmacy, last_name="Morin-Demo").delete()
        self.stdout.write(self.style.SUCCESS("Données démo supprimées."))

    # ── Seed ───────────────────────────────────────────────────────────────────

    def _seed(self, pharmacy):
        marc   = Collaborator.objects.get(pharmacy=pharmacy, last_name="Dupont")
        julie  = Collaborator.objects.get(pharmacy=pharmacy, last_name="Bernard")
        thomas = Collaborator.objects.get(pharmacy=pharmacy, last_name="Leroy")
        alain, created = Collaborator.objects.get_or_create(
            pharmacy=pharmacy, last_name="Morin-Demo",
            defaults=dict(
                civility="Dr.", first_name="Alain", role="Titulaire",
                color="#10b981", weekly_hours=35, is_tns=True, is_active=True,
            ),
        )
        if created:
            self.stdout.write("  → Dr. Alain Morin-Demo (TNS) créé")

        # Purge novembre existant pour ces collab
        for c in [marc, julie, thomas, alain]:
            Shift.objects.filter(
                collaborator=c,
                start_datetime__date__gte=date(2026, 11, 1),
                start_datetime__date__lte=date(2026, 12, 6),
            ).delete()
            TimeAdjustment.objects.filter(
                collaborator=c,
                date__gte=date(2026, 11, 1),
                date__lte=date(2026, 11, 30),
            ).delete()
            AbsenceRequest.objects.filter(
                collaborator=c,
                start_date__gte=date(2026, 11, 1),
                start_date__lte=date(2026, 11, 30),
            ).delete()

        shifts_to_create = []

        # ── Marc Dupont ────────────────────────────────────────────────────────

        # Nov 1 Toussaint (dimanche) : shift travaillé → jour férié + dimanche
        shifts_to_create.append(shift(marc, date(2026, 11, 1), 10, 14))

        # S45 (2-8 nov) : Lun-Ven 9h-17h = 40h
        for d in [2, 3, 4, 5, 6]:
            shifts_to_create.append(shift(marc, date(2026, 11, d), 9, 17))

        # S46 (9-15 nov) : Lun-Dim 9h-17h = 7j/56h → alerte_46h + alerte_6j
        # Inclut Nov 11 Armistice (mer) travaillé
        for d in [9, 10, 11, 12, 13, 14, 15]:
            shifts_to_create.append(shift(marc, date(2026, 11, d), 9, 17))

        # S47 (16-22 nov) : CP lun-ven
        AbsenceRequest.objects.create(
            collaborator=marc,
            type="cp",
            status="approved",
            start_date=date(2026, 11, 16),
            end_date=date(2026, 11, 20),
            working_days_count=5,
        )

        # S48 (23-29 nov) : Lun-Ven 9h-17h + overtime jeu 26 +3h
        for d in [23, 24, 25, 26, 27]:
            shifts_to_create.append(shift(marc, date(2026, 11, d), 9, 17))
        TimeAdjustment.objects.create(
            collaborator=marc,
            date=date(2026, 11, 26),
            type="overtime",
            reference_time=time(17, 0),
            actual_time=time(20, 0),
            duration_minutes=180,
            note="Inventaire de fin de mois",
        )

        # S49 a_cheval : lun 30 nov
        shifts_to_create.append(shift(marc, date(2026, 11, 30), 9, 17))

        # ── Julie Bernard ──────────────────────────────────────────────────────

        # S45 (2-8 nov) : Nuit Lun-Ven 20h-04h (8h, cross-midnight)
        for d in [2, 3, 4, 5, 6]:
            shifts_to_create.append(
                shift(julie, date(2026, 11, d), 20, 4,
                      end_date=date(2026, 11, d + 1))
            )

        # S46 (9-15 nov)
        # Lun 9 : présent
        shifts_to_create.append(shift(julie, date(2026, 11, 9), 9, 17))
        # Mar 10 : absence injustifiée
        shifts_to_create.append(shift(julie, date(2026, 11, 10), 9, 17,
                                       absent=True, abs_type="injustifiee"))
        # Mer 11 Armistice : travaillé (jour férié)
        shifts_to_create.append(shift(julie, date(2026, 11, 11), 9, 17))
        # Jeu 12 : shift + départ anticipé -2h
        shifts_to_create.append(shift(julie, date(2026, 11, 12), 9, 17))
        TimeAdjustment.objects.create(
            collaborator=julie,
            date=date(2026, 11, 12),
            type="early_departure",
            reference_time=time(17, 0),
            actual_time=time(15, 0),
            duration_minutes=120,
            note="RDV médical",
        )
        # Ven 13 : présent
        shifts_to_create.append(shift(julie, date(2026, 11, 13), 9, 17))

        # S47 (16-22 nov) : Formation lun-ven
        AbsenceRequest.objects.create(
            collaborator=julie,
            type="formation",
            status="approved",
            start_date=date(2026, 11, 16),
            end_date=date(2026, 11, 20),
            working_days_count=5,
        )

        # S48 (23-29 nov) : Lun-Ven 9h-17h + dim 29 10h-14h
        for d in [24, 25, 26, 27, 28]:
            shifts_to_create.append(shift(julie, date(2026, 11, d), 9, 17))
        shifts_to_create.append(shift(julie, date(2026, 11, 29), 10, 14))  # dimanche

        # S49 a_cheval
        shifts_to_create.append(shift(julie, date(2026, 11, 30), 9, 17))

        # ── Thomas Leroy ───────────────────────────────────────────────────────

        # S45 (2-8 nov) : Lun-Dim 9h-17h = 7j → alerte_6j + alerte_46h + dimanche
        for d in [2, 3, 4, 5, 6, 7, 8]:
            shifts_to_create.append(shift(thomas, date(2026, 11, d), 9, 17))

        # S46 (9-15 nov) : Lun + Ven 9h-20h30 (11.5h chacun) → alerte_10h + alerte_46h
        # Mar-Jeu 9h-17h (8h chacun)
        shifts_to_create.append(
            shift(thomas, date(2026, 11, 9), 9, 20,   # end=20h30 géré ci-dessous
                  end_date=date(2026, 11, 9))
        )
        # Fix : on crée manuellement les shifts à 20h30
        shifts_to_create[-1].end_datetime = dt(date(2026, 11, 9), 20, 30)
        for d in [10, 11, 12]:
            shifts_to_create.append(shift(thomas, date(2026, 11, d), 9, 17))
        shifts_to_create.append(shift(thomas, date(2026, 11, 13), 9, 17))
        shifts_to_create[-1].end_datetime = dt(date(2026, 11, 13), 20, 30)

        # S47 (16-22 nov) : RCR lun-ven
        AbsenceRequest.objects.create(
            collaborator=thomas,
            type="rcr",
            status="approved",
            start_date=date(2026, 11, 16),
            end_date=date(2026, 11, 20),
            working_days_count=5,
        )

        # S48 (23-29 nov) : Lun-Ven 9h-17h → 40h, sup=20h (base 20h), tr1=8h, tr2=12h
        for d in [23, 24, 25, 26, 27]:
            shifts_to_create.append(shift(thomas, date(2026, 11, d), 9, 17))

        # S49 a_cheval
        shifts_to_create.append(shift(thomas, date(2026, 11, 30), 9, 17))

        # ── Alain Morin (TNS) ──────────────────────────────────────────────────

        for week_start in [2, 9, 16, 23]:
            for d in range(week_start, week_start + 5):
                if d <= 30:
                    shifts_to_create.append(shift(alain, date(2026, 11, d), 9, 17))
        shifts_to_create.append(shift(alain, date(2026, 11, 30), 9, 17))  # a_cheval

        # ── Bulk create ────────────────────────────────────────────────────────
        Shift.objects.bulk_create(shifts_to_create)

        total = len(shifts_to_create)
        self.stdout.write(self.style.SUCCESS(
            f"\n✓ {total} shifts publiés pour novembre 2026\n"
            f"\n  Marc Dupont    : S45 standard · S46 7j/56h ⚠46h⚠6j · S47 CP · S48 OT · Toussaint+Armistice travaillés"
            f"\n  Julie Bernard  : S45 nuit · S46 abs.injust+départ anticipé+Armistice · S47 Formation · S48 dimanche"
            f"\n  Thomas Leroy   : S45 7j/56h ⚠46h⚠6j · S46 ⚠10h ⚠46h · S47 RCR · S48 40h/base20h tr2"
            f"\n  Alain Morin    : TNS lun-ven standard"
            f"\n\nSupprimer : python manage.py seed_paye_novembre --flush"
        ))
