import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface CorrectiveActionSuggestion {
  description: string;
  delai: string;
}

@Injectable({ providedIn: 'root' })
export class AiService {
  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/quality/ai`;

  generateProcedureContent(payload: {
    title: string;
    category: string;
    reference: string;
    context?: string;
  }): Observable<{ content: string }> {
    return this.http.post<{ content: string }>(`${this.api}/generate-procedure/`, payload);
  }

  refactorText(payload: {
    text: string;
    mode: 'selection' | 'full';
  }): Observable<{ result: string }> {
    return this.http.post<{ result: string }>(`${this.api}/refactor-text/`, payload);
  }

  suggestCorrectiveActions(payload: {
    nc_title: string;
    nc_description: string;
    severity: string;
  }): Observable<{ actions: CorrectiveActionSuggestion[] }> {
    return this.http.post<{ actions: CorrectiveActionSuggestion[] }>(
      `${this.api}/suggest-actions/`,
      payload,
    );
  }
}
