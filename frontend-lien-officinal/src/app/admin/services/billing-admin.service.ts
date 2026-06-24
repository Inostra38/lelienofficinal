import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AdminSubscription {
  plan: string;
  plan_display: string;
  status: string;
  status_display: string;
  is_comp: boolean;
  trial_ends_at: string | null;
  current_period_end: string | null;
}

export interface AdminPharmacyRow {
  pharmacy_id: number;
  email: string;
  nom_officine: string;
  sms_credits: number;
  subscription: AdminSubscription | null;
}

export interface AdminInvoice {
  id: number;
  invoice_number: string;
  invoice_type: string;
  amount_ttc: string;
  issued_at: string;
  paid_at: string | null;
}

export interface AdminPharmacyDetail extends AdminPharmacyRow {
  invoices: AdminInvoice[];
}

export interface AdminPromoCode {
  id: number;
  code: string;
  months_free: number;
  is_active: boolean;
  max_uses: number | null;
  current_uses: number;
  expires_at: string | null;
  note: string;
  created_at: string;
}

@Injectable({ providedIn: 'root' })
export class BillingAdminService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/api/admin`;

  listSubscriptions(q = ''): Observable<{ count: number; results: AdminPharmacyRow[] }> {
    return this.http.get<{ count: number; results: AdminPharmacyRow[] }>(
      `${this.base}/subscriptions/`,
      { params: q ? { q } : {} },
    );
  }

  getSubscription(pharmacyId: number): Observable<AdminPharmacyDetail> {
    return this.http.get<AdminPharmacyDetail>(`${this.base}/subscriptions/${pharmacyId}/`);
  }

  action(pharmacyId: number, action: string, plan?: string): Observable<AdminPharmacyRow> {
    return this.http.post<AdminPharmacyRow>(
      `${this.base}/subscriptions/${pharmacyId}/action/`,
      { action, ...(plan ? { plan } : {}) },
    );
  }

  listPromoCodes(): Observable<AdminPromoCode[]> {
    return this.http.get<AdminPromoCode[]>(`${this.base}/promo-codes/`);
  }

  createPromoCode(body: {
    code: string; months_free: number; max_uses?: number | null; note?: string;
  }): Observable<AdminPromoCode> {
    return this.http.post<AdminPromoCode>(`${this.base}/promo-codes/`, body);
  }

  togglePromoCode(id: number, is_active: boolean): Observable<AdminPromoCode> {
    return this.http.patch<AdminPromoCode>(`${this.base}/promo-codes/${id}/`, { is_active });
  }

  deletePromoCode(id: number): Observable<void> {
    return this.http.delete<void>(`${this.base}/promo-codes/${id}/`);
  }
}
