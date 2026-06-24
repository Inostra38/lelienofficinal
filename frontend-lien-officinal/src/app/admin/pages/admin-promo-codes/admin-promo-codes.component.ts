import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { BillingAdminService, AdminPromoCode } from '../../services/billing-admin.service';

@Component({
  selector: 'app-admin-promo-codes',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin-promo-codes.component.html',
})
export class AdminPromoCodesComponent implements OnInit {
  private svc = inject(BillingAdminService);

  codes = signal<AdminPromoCode[]>([]);
  loading = signal(false);
  error = signal<string | null>(null);

  // Formulaire de création
  newCode = signal('');
  newMonths = signal(1200);
  newMaxUses = signal<number | null>(10);
  newNote = signal('');
  creating = signal(false);

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.svc.listPromoCodes().subscribe({
      next: (c) => { this.codes.set(c); this.loading.set(false); },
      error: () => { this.error.set('Erreur de chargement.'); this.loading.set(false); },
    });
  }

  create() {
    const code = this.newCode().trim().toUpperCase();
    if (!code || this.newMonths() < 1) return;
    this.creating.set(true);
    this.error.set(null);
    this.svc.createPromoCode({
      code,
      months_free: this.newMonths(),
      max_uses: this.newMaxUses(),
      note: this.newNote(),
    }).subscribe({
      next: (c) => {
        this.codes.update((cs) => [c, ...cs]);
        this.newCode.set('');
        this.newNote.set('');
        this.creating.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.error ?? 'Création impossible.');
        this.creating.set(false);
      },
    });
  }

  toggle(c: AdminPromoCode) {
    this.svc.togglePromoCode(c.id, !c.is_active).subscribe({
      next: (u) => this.codes.update((cs) => cs.map((x) => (x.id === u.id ? u : x))),
    });
  }

  remove(c: AdminPromoCode) {
    if (!confirm(`Supprimer le code ${c.code} ?`)) return;
    this.svc.deletePromoCode(c.id).subscribe({
      next: () => this.codes.update((cs) => cs.filter((x) => x.id !== c.id)),
    });
  }

  yearsLabel(months: number): string {
    return `≈ ${Math.round((months * 30) / 365)} ans`;
  }
}
