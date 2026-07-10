import { Injectable, inject, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';

export interface SmsStatusUpdate {
  type: 'sms_status_update';
  log_id: string;
  status: string;
  updated_at: string;
}

const WS_BACKOFF_INITIAL = 3_000;
const WS_BACKOFF_MAX = 30_000;

@Injectable({ providedIn: 'root' })
export class SmsWebSocketService implements OnDestroy {
  private authService = inject(AuthService);
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;
  private backoffDelay = WS_BACKOFF_INITIAL;

  readonly statusUpdates$ = new Subject<SmsStatusUpdate>();

  connect(): void {
    this.disconnect();
    const token = this.authService.getToken();
    if (token) {
      this._doConnect(token);
    } else if (this.authService.isAuthenticated()) {
      // Reload : _accessToken null mais cookie session_info valide — refresh d'abord
      this.authService.refreshAccessToken().subscribe({
        next: t => this._doConnect(t),
        error: () => {}
      });
    }
  }

  private _doConnect(token: string): void {
    this.shouldReconnect = true;
    // Jeton en sous-protocole (le middleware ne lit que ça ; un jeton en query
    // string finit dans les logs serveur/proxy). Cohérent avec la messagerie.
    const url = `${environment.wsUrl}/ws/sms/status/`;
    this.socket = new WebSocket(url, ['bearer', token]);

    this.socket.onopen = () => {
      this.backoffDelay = WS_BACKOFF_INITIAL; // reset au succès
    };

    this.socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'sms_status_update') {
          this.statusUpdates$.next(data as SmsStatusUpdate);
        }
      } catch {
        // message mal formé — ignorer
      }
    };

    this.socket.onclose = (evt) => {
      if (this.shouldReconnect && evt.code !== 1000 && evt.code !== 4001 && evt.code !== 4003) {
        this.reconnectTimer = setTimeout(() => this.connect(), this.backoffDelay);
        this.backoffDelay = Math.min(this.backoffDelay * 2, WS_BACKOFF_MAX);
      }
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
    this.backoffDelay = WS_BACKOFF_INITIAL;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.socket) {
      this.socket.close(1000);
      this.socket = null;
    }
  }

  ngOnDestroy(): void {
    this.disconnect();
    this.statusUpdates$.complete();
  }
}
