import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import {
  BillingAdminService,
  AdminPharmacyRow,
  AdminPharmacyDetail,
} from '../../services/billing-admin.service';

@Component({
  selector: 'app-admin-subscriptions',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './admin-subscriptions.component.html',
})
export class AdminSubscriptionsComponent implements OnInit {
  private svc = inject(BillingAdminService);

  rows = signal<AdminPharmacyRow[]>([]);
  count = signal(0);
  query = signal('');
  loading = signal(false);
  busyId = signal<number | null>(null);
  detail = signal<AdminPharmacyDetail | null>(null);
  error = signal<string | null>(null);

  ngOnInit() {
    this.load();
  }

  load() {
    this.loading.set(true);
    this.error.set(null);
    this.svc.listSubscriptions(this.query().trim()).subscribe({
      next: (res) => {
        this.rows.set(res.results);
        this.count.set(res.count);
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Erreur de chargement.');
        this.loading.set(false);
      },
    });
  }

  act(row: AdminPharmacyRow, action: string, plan?: string) {
    if (action === 'revoke' && !confirm(`Révoquer l'abonnement offert de ${row.email} ?`)) return;
    this.busyId.set(row.pharmacy_id);
    this.error.set(null);
    this.svc.action(row.pharmacy_id, action, plan).subscribe({
      next: (updated) => {
        this.rows.update((rs) =>
          rs.map((r) => (r.pharmacy_id === updated.pharmacy_id ? updated : r)),
        );
        if (this.detail()?.pharmacy_id === updated.pharmacy_id) {
          this.openDetail(updated);
        }
        this.busyId.set(null);
      },
      error: (e) => {
        this.error.set(e?.error?.error ?? 'Action impossible.');
        this.busyId.set(null);
      },
    });
  }

  openDetail(row: AdminPharmacyRow) {
    this.svc.getSubscription(row.pharmacy_id).subscribe({
      next: (d) => this.detail.set(d),
    });
  }

  closeDetail() {
    this.detail.set(null);
  }

  badgeClass(status: string | undefined): string {
    const base = 'px-2 py-0.5 rounded-full text-xs font-medium';
    const map: Record<string, string> = {
      active: 'bg-green-100 text-green-800',
      trialing: 'bg-green-50 text-green-700',
      past_due: 'bg-amber-100 text-amber-700',
      suspended: 'bg-red-100 text-red-700',
      canceled: 'bg-gray-100 text-gray-500',
    };
    return `${base} ${map[status ?? ''] ?? 'bg-gray-100 text-gray-500'}`;
  }
}
