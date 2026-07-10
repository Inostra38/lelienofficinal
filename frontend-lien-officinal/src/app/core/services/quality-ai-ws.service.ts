import { Injectable, inject, OnDestroy } from '@angular/core';
import { Observable, Subject, throwError, of } from 'rxjs';
import { filter, take, timeout, switchMap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';

interface WsMessage {
  type: 'result' | 'error';
  request_id: string;
  status?: string;
  message?: string;
  [key: string]: unknown;
}

/**
 * Service WebSocket pour les appels IA du module qualité.
 *
 * Ouvre une connexion lazy sur /ws/quality/ai/ et expose une méthode
 * request() qui retourne un Observable — même contrat que HttpClient.
 *
 * L'appel Anthropic est exécuté de façon async côté serveur (AsyncAnthropic)
 * sans bloquer Daphne. Timeout côté client : 90s.
 */
@Injectable({ providedIn: 'root' })
export class QualityAiWsService implements OnDestroy {
  private authService = inject(AuthService);

  private socket: WebSocket | null = null;
  private readonly messages$ = new Subject<WsMessage>();
  private connectingPromise: Promise<void> | null = null;

  // ── Connexion lazy ────────────────────────────────────────────────────

  private ensureConnected(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN) {
      return Promise.resolve();
    }
    if (this.connectingPromise) {
      return this.connectingPromise;
    }

    this.connectingPromise = new Promise((resolve, reject) => {
      const token = this.authService.getToken();
      if (!token) {
        reject(new Error('Non authentifié.'));
        return;
      }

      // Jeton en sous-protocole (le middleware ne lit que ça ; un jeton en
      // query string finit dans les logs). Cohérent avec la messagerie.
      const url = `${environment.wsUrl}/ws/quality/ai/`;
      const ws  = new WebSocket(url, ['bearer', token]);

      ws.onopen = () => {
        this.socket            = ws;
        this.connectingPromise = null;
        resolve();
      };

      ws.onmessage = (evt) => {
        try {
          this.messages$.next(JSON.parse(evt.data) as WsMessage);
        } catch { /* ignore malformed frames */ }
      };

      ws.onerror = () => {
        this.connectingPromise = null;
        reject(new Error('Connexion WebSocket IA impossible.'));
      };

      ws.onclose = () => {
        this.socket            = null;
        this.connectingPromise = null;
      };
    });

    return this.connectingPromise;
  }

  // ── API publique ───────────────────────────────────────────────────────

  /**
   * Envoie une requête IA et retourne un Observable qui émet le résultat
   * quand le serveur répond (ou erreur après 90 secondes).
   */
  request<T>(type: string, payload: object): Observable<T> {
    const requestId = crypto.randomUUID();

    return new Observable<T>(observer => {
      this.ensureConnected()
        .then(() => {
          // Écoute la réponse avant d'envoyer (évite une race condition)
          const sub = this.messages$.pipe(
            filter(m => m.request_id === requestId),
            take(1),
            timeout(90_000),
            switchMap(m =>
              m.type === 'error'
                ? throwError(() => new Error(m.message ?? 'Erreur IA inconnue.'))
                : of(m as unknown as T)
            ),
          ).subscribe(observer);

          this.socket!.send(JSON.stringify({ type, request_id: requestId, ...payload }));

          return () => sub.unsubscribe();
        })
        .catch(err => observer.error(err));
    });
  }

  // ── Nettoyage ─────────────────────────────────────────────────────────

  ngOnDestroy(): void {
    this.socket?.close(1000);
    this.messages$.complete();
  }
}
