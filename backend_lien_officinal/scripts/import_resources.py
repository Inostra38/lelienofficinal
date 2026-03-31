"""
Import ResourceCard et ResourceItem depuis ressources_pharmacie_DB.xlsx.

Usage :
    python scripts/import_resources.py /chemin/vers/ressources_pharmacie_DB.xlsx

Options :
    --dry-run   Affiche les opérations sans toucher la base
"""
import os
import sys
import argparse
import django

# ── Bootstrap Django ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend_lien_officinal.settings')
django.setup()

# ── Imports après setup ───────────────────────────────────────────────────────
import openpyxl
from django.db import transaction

from apps.resources.models import ResourceCard, ResourceItem

# ── Helpers ───────────────────────────────────────────────────────────────────

def parse_nullable(value):
    """Retourne None si la valeur est 'NULL', None ou vide."""
    if value is None:
        return None
    if str(value).strip().upper() == 'NULL':
        return None
    return value


def import_cards(ws, dry_run: bool) -> tuple[int, int, int]:
    created = updated = skipped = 0

    for row in ws.iter_rows(min_row=2, values_only=True):
        row_id, titre, description_officielle, card_type, owner_partner_id, owner_pharmacy_id, icon_url, is_featured, ordre, categorie_display = row

        if row_id is None:
            continue

        owner_partner_id = parse_nullable(owner_partner_id)
        owner_pharmacy_id = parse_nullable(owner_pharmacy_id)

        defaults = {
            'titre': titre or '',
            'description_officielle': description_officielle or '',
            'type': card_type or 'OFFICIAL',
            'owner_partner_id': owner_partner_id,
            'owner_pharmacy_id': owner_pharmacy_id,
            'is_featured': bool(is_featured),
            'ordre': int(ordre) if ordre is not None else 0,
        }

        if dry_run:
            exists = ResourceCard.objects.filter(pk=row_id).exists()
            action = '[UPDATED]' if exists else '[CREATED]'
            print(f"  {action} Card pk={row_id} — {titre}")
            if exists:
                updated += 1
            else:
                created += 1
            continue

        obj, was_created = ResourceCard.objects.update_or_create(
            pk=row_id,
            defaults=defaults,
        )
        if was_created:
            print(f"  [CREATED] Card pk={obj.pk} — {obj.titre}")
            created += 1
        else:
            print(f"  [UPDATED] Card pk={obj.pk} — {obj.titre}")
            updated += 1

    return created, updated, skipped


def import_items(ws, dry_run: bool) -> tuple[int, int, int]:
    created = updated = skipped = 0

    # Précharger les ids de cartes existantes pour détecter les orphelins
    if not dry_run:
        valid_card_ids = set(ResourceCard.objects.values_list('pk', flat=True))
    else:
        valid_card_ids = None  # en dry-run on fait confiance au fichier

    for row in ws.iter_rows(min_row=2, values_only=True):
        row_id, card_id, card_titre, item_type, label, url_or_file = row

        if row_id is None:
            continue

        if card_id is None:
            print(f"  [SKIPPED] Item pk={row_id} — card_id manquant")
            skipped += 1
            continue

        card_id = int(card_id)

        if valid_card_ids is not None and card_id not in valid_card_ids:
            print(f"  [SKIPPED] Item pk={row_id} — Card pk={card_id} introuvable ('{card_titre}')")
            skipped += 1
            continue

        url_val = url_or_file or ''
        # Les fichiers PDF seront importés manuellement — on stocke le nom brut dans url
        defaults = {
            'card_id': card_id,
            'type': item_type or 'WEB',
            'label': label or '',
            'url': url_val if item_type != 'PDF' else '',
            'ordre': 0,
        }

        if dry_run:
            exists = ResourceItem.objects.filter(pk=row_id).exists()
            action = '[UPDATED]' if exists else '[CREATED]'
            print(f"  {action} Item pk={row_id} — [{item_type}] {label} (Card: {card_titre})")
            if exists:
                updated += 1
            else:
                created += 1
            continue

        obj, was_created = ResourceItem.objects.update_or_create(
            pk=row_id,
            defaults=defaults,
        )
        if was_created:
            print(f"  [CREATED] Item pk={obj.pk} — [{obj.type}] {obj.label}")
            created += 1
        else:
            print(f"  [UPDATED] Item pk={obj.pk} — [{obj.type}] {obj.label}")
            updated += 1

    return created, updated, skipped


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import ressources depuis Excel")
    parser.add_argument('file', help="Chemin vers ressources_pharmacie_DB.xlsx")
    parser.add_argument('--dry-run', action='store_true', help="Simulation sans écriture en base")
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"ERREUR : fichier introuvable → {args.file}")
        sys.exit(1)

    wb = openpyxl.load_workbook(args.file)

    if 'resource_card' not in wb.sheetnames or 'resource_item' not in wb.sheetnames:
        print(f"ERREUR : onglets attendus 'resource_card' et 'resource_item' non trouvés.")
        print(f"Onglets présents : {wb.sheetnames}")
        sys.exit(1)

    mode = "DRY-RUN" if args.dry_run else "IMPORT"
    print(f"\n{'='*60}")
    print(f"  {mode} — ResourceCard")
    print(f"{'='*60}")

    if args.dry_run:
        c_created, c_updated, c_skipped = import_cards(wb['resource_card'], dry_run=True)
    else:
        with transaction.atomic():
            c_created, c_updated, c_skipped = import_cards(wb['resource_card'], dry_run=False)

    print(f"\n  → Cartes : {c_created} créées, {c_updated} mises à jour, {c_skipped} ignorées")

    print(f"\n{'='*60}")
    print(f"  {mode} — ResourceItem")
    print(f"{'='*60}")

    if args.dry_run:
        i_created, i_updated, i_skipped = import_items(wb['resource_item'], dry_run=True)
    else:
        with transaction.atomic():
            i_created, i_updated, i_skipped = import_items(wb['resource_item'], dry_run=False)

    print(f"\n  → Items : {i_created} créés, {i_updated} mis à jour, {i_skipped} ignorés")

    print(f"\n{'='*60}")
    print(f"  TOTAL : {c_created + i_created} créés, {c_updated + i_updated} mis à jour, {c_skipped + i_skipped} ignorés")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
