import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface SmsTemplate {
  id: number;
  title: string;
  content: string;
  created_at: string;
  updated_at: string;
}

export interface SmsPreviewResponse {
  preview_text: string;
  missing_vars: string[];
  sms_count: number;
  encoding: 'GSM-7' | 'Unicode';
}

export type SmsStatus = 'PENDING' | 'SUCCESS' | 'DELIVERED' | 'FAILED';

export interface SmsLog {
  id: number;
  template_title: string;
  sent_by_display: string;
  recipient_civilite: string;
  recipient_name: string;
  to_hash: string;
  status: SmsStatus;
  status_label: string;
  ovh_message_id: string;
  credits_used: number;
  sent_at: string;
  error_message: string;
  motif: string;
}

export interface SmsSendResponse {
  log_id: number;
  credits_remaining: number;
}

@Injectable({ providedIn: 'root' })
export class SmsService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/sms`;

  // ── Templates ─────────────────────────────────────────────────────────────

  getTemplates(): Observable<SmsTemplate[]> {
    return this.http.get<SmsTemplate[]>(`${this.apiUrl}/templates/`);
  }

  createTemplate(data: Partial<SmsTemplate>): Observable<SmsTemplate> {
    return this.http.post<SmsTemplate>(`${this.apiUrl}/templates/`, data);
  }

  updateTemplate(id: number, data: Partial<SmsTemplate>): Observable<SmsTemplate> {
    return this.http.patch<SmsTemplate>(`${this.apiUrl}/templates/${id}/`, data);
  }

  deleteTemplate(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/templates/${id}/`);
  }

  // ── Preview & Send ─────────────────────────────────────────────────────────

  preview(payload: {
    template_id?: number;
    content?: string;
    custom_vars?: Record<string, string>;
  }): Observable<SmsPreviewResponse> {
    return this.http.post<SmsPreviewResponse>(`${this.apiUrl}/preview/`, payload);
  }

  send(payload: {
    to: string;
    message: string;
    template_id?: number;
    recipient_civilite?: string;
    recipient_name?: string;
    motif?: string;
  }): Observable<SmsSendResponse> {
    return this.http.post<SmsSendResponse>(`${this.apiUrl}/send/`, payload);
  }

  // ── Logs ──────────────────────────────────────────────────────────────────

  getLogs(): Observable<SmsLog[]> {
    return this.http.get<SmsLog[]>(`${this.apiUrl}/logs/`);
  }

  // ── Crédits ───────────────────────────────────────────────────────────────

  getCredits(): Observable<{ credits: number }> {
    return this.http.get<{ credits: number }>(`${this.apiUrl}/credits/`);
  }
}
