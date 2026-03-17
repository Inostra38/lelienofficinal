import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { NonConformity, CorrectiveAction } from '../models/nonconformity.model';

@Injectable({ providedIn: 'root' })
export class QualityNcService {
  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/quality`;

  getNonConformities(filters?: { status?: string; severity?: string }): Observable<NonConformity[]> {
    let params = new HttpParams();
    if (filters?.status) params = params.set('status', filters.status);
    if (filters?.severity) params = params.set('severity', filters.severity);
    return this.http.get<NonConformity[]>(`${this.api}/nonconformities/`, { params });
  }

  getNonConformity(id: number): Observable<NonConformity> {
    return this.http.get<NonConformity>(`${this.api}/nonconformities/${id}/`);
  }

  createNonConformity(data: Partial<NonConformity>): Observable<NonConformity> {
    return this.http.post<NonConformity>(`${this.api}/nonconformities/`, data);
  }

  updateNonConformity(id: number, data: Partial<NonConformity>): Observable<NonConformity> {
    return this.http.patch<NonConformity>(`${this.api}/nonconformities/${id}/`, data);
  }

  assignNonConformity(id: number, collaboratorId: number): Observable<NonConformity> {
    return this.http.post<NonConformity>(`${this.api}/nonconformities/${id}/assign/`, { assigned_to: collaboratorId });
  }

  closeNonConformity(id: number, resolution?: string): Observable<NonConformity> {
    return this.http.post<NonConformity>(`${this.api}/nonconformities/${id}/close/`, { resolution: resolution || '' });
  }

  reopenNonConformity(id: number): Observable<NonConformity> {
    return this.http.post<NonConformity>(`${this.api}/nonconformities/${id}/reopen/`, {});
  }

  createCorrectiveAction(data: { nonconformity: number; description: string; responsible?: number; due_date?: string }): Observable<CorrectiveAction> {
    return this.http.post<CorrectiveAction>(`${this.api}/actions/`, data);
  }

  updateCorrectiveAction(id: number, data: Partial<CorrectiveAction>): Observable<CorrectiveAction> {
    return this.http.patch<CorrectiveAction>(`${this.api}/actions/${id}/`, data);
  }
}
