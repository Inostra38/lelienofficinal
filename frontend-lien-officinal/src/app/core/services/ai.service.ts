import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { QualityAiWsService } from './quality-ai-ws.service';

export interface CorrectiveActionSuggestion {
  description: string;
  delai: string;
}

/**
 * Service IA pour le module qualité.
 * Délègue au QualityAiWsService (WebSocket async) — non bloquant.
 */
@Injectable({ providedIn: 'root' })
export class AiService {
  private ws = inject(QualityAiWsService);

  refactorText(payload: {
    text: string;
    mode: 'selection' | 'full';
  }): Observable<{ result: string }> {
    return this.ws.request<{ result: string }>('refactor_text', payload);
  }

  suggestCorrectiveActions(payload: {
    nc_title: string;
    nc_description: string;
    severity: string;
  }): Observable<{ actions: CorrectiveActionSuggestion[] }> {
    return this.ws.request<{ actions: CorrectiveActionSuggestion[] }>(
      'suggest_actions',
      payload,
    );
  }
}
