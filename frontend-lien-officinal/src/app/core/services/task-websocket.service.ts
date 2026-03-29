import { Injectable, inject, OnDestroy } from '@angular/core';
import { Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../auth/auth.service';

@Injectable({ providedIn: 'root' })
export class TaskWebSocketService implements OnDestroy {
  private authService = inject(AuthService);
  private socket: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private shouldReconnect = false;

  /** Émet void à chaque notification de mise à jour reçue. */
  readonly events$ = new Subject<void>();

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
    const url = `${environment.wsUrl}/ws/tasks/?token=${encodeURIComponent(token)}`;
    this.socket = new WebSocket(url);

    this.socket.onmessage = () => {
      this.events$.next();
    };

    this.socket.onclose = (evt) => {
      if (this.shouldReconnect && evt.code !== 1000 && evt.code !== 4001 && evt.code !== 4003) {
        this.reconnectTimer = setTimeout(() => this.connect(), 3000);
      }
    };
  }

  disconnect(): void {
    this.shouldReconnect = false;
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
    this.events$.complete();
  }
}
