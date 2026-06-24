import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SubscriptionStatus {
  plan: 'small' | 'large';
  status: 'trialing' | 'active' | 'past_due' | 'suspended' | 'canceled';
  trial_ends_at: string | null;
  current_period_end: string | null;
  is_access_allowed: boolean;
}

export interface BillingStatusResponse {
  subscription: SubscriptionStatus | null;
  sms_credit: { balance: number };
}

export interface Invoice {
  id: number;
  invoice_number: string;
  invoice_type: 'subscription' | 'sms_pack';
  amount_ht: string;
  tva_rate: string;
  amount_ttc: string;
  issued_at: string;
  paid_at: string | null;
}

@Injectable({ providedIn: 'root' })
export class BillingService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/api/billing`;

  getStatus(): Observable<BillingStatusResponse> {
    return this.http.get<BillingStatusResponse>(`${this.base}/status/`);
  }

  setupSubscription(): Observable<{ client_secret: string }> {
    return this.http.post<{ client_secret: string }>(`${this.base}/setup/`, {});
  }

  confirmSubscription(
    payment_method_id: string,
    promo_code?: string,
  ): Observable<{ status: string; plan: string }> {
    return this.http.post<{ status: string; plan: string }>(`${this.base}/confirm/`, {
      payment_method_id,
      ...(promo_code ? { promo_code } : {}),
    });
  }

  validatePromoCode(code: string): Observable<{
    valid: boolean;
    months_free?: number;
    trial_days?: number;
    message?: string;
  }> {
    return this.http.post<any>(`${this.base}/promo/validate/`, { code });
  }

  createSmsPackIntent(pack: 'S' | 'M' | 'L'): Observable<{
    client_secret: string;
    quantity: number;
    amount_cents: number;
  }> {
    return this.http.post<any>(`${this.base}/sms-pack/intent/`, { pack });
  }

  getInvoices(): Observable<Invoice[]> {
    return this.http.get<Invoice[]>(`${this.base}/invoices/`);
  }
}
