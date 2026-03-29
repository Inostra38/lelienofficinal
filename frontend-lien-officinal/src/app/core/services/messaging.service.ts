import { Injectable, inject, OnDestroy } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { environment } from '../../../environments/environment';
import { Collaborator } from './collaborator.service';
import { AuthService } from '../auth/auth.service';

// ── Interfaces ────────────────────────────────────────────────────────────────

export interface CollaboratorMinimal {
  id: number;
  first_name: string;
  last_name: string;
  full_name: string;
  role: string;
  color: string;
}

export interface LastMessage {
  sender: string;
  content: string;
  created_at: string;
}

export interface Conversation {
  id: string;
  subject: string;
  created_by: CollaboratorMinimal;
  participants: CollaboratorMinimal[];
  last_message: LastMessage | null;
  unread_count: number;
  created_at: string;
  updated_at: string;
}

export interface Message {
  id: string;
  sender: CollaboratorMinimal;
  content: string;
  is_read_by: CollaboratorMinimal[];
  created_at: string;
}

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

// ── Service ───────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class MessagingService implements OnDestroy {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/messaging`;
  private wsUrl = environment.wsUrl;

  private socket: WebSocket | null = null;
  private currentConversationId: string | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  /** Compteur global de messages non lus — partagé avec la sidebar du dashboard. */
  readonly unreadCount$ = new BehaviorSubject<number>(0);
  readonly messages$ = new Subject<Message>();
  readonly wsStatus$ = new BehaviorSubject<WebSocketStatus>('disconnected');

  setUnreadCount(count: number): void {
    this.unreadCount$.next(count);
  }

  // ── Collaborateur actif — délégué à AuthService (source de vérité unique) ─

  setActiveCollaboratorId(id: number): void {
    this.authService.setCurrentCollaboratorId(id);
  }

  getActiveCollaboratorId(): number | null {
    return this.authService.getCurrentCollaboratorId();
  }

  clearActiveCollaborator(): void {
    this.authService.clearCurrentCollaborator();
  }

  // ── Conversations (REST) ──────────────────────────────────────────────────

  getConversations(): Observable<Conversation[]> {
    return this.http.get<Conversation[]>(`${this.apiUrl}/conversations/`);
  }

  getConversation(id: string): Observable<Conversation> {
    return this.http.get<Conversation>(`${this.apiUrl}/conversations/${id}/`);
  }

  createConversation(subject: string, participantIds: number[]): Observable<Conversation> {
    return this.http.post<Conversation>(
      `${this.apiUrl}/conversations/`,
      { subject, participant_ids: participantIds }
    );
  }

  deleteConversation(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/conversations/${id}/`);
  }

  hideConversation(id: string): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/conversations/${id}/hide/`, {});
  }

  // ── Messages (REST — historique initial) ─────────────────────────────────

  getMessages(conversationId: string): Observable<Message[]> {
    return this.http.get<Message[]>(`${this.apiUrl}/conversations/${conversationId}/messages/`);
  }

  markAsRead(conversationId: string): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/conversations/${conversationId}/mark-read/`, {});
  }

  // ── Équipe ───────────────────────────────────────────────────────────────

  getTeamMembers(): Observable<Collaborator[]> {
    return this.http.get<Collaborator[]>(`${this.apiUrl}/team-members/`);
  }

  // ── WebSocket ─────────────────────────────────────────────────────────────

  connectToConversation(conversationId: string): void {
    this.disconnect(); // ferme la connexion précédente proprement

    const token = this.authService.getToken();
    if (token) {
      this._doConnectToConversation(conversationId, token);
    } else if (this.authService.isAuthenticated()) {
      // Reload : _accessToken null mais cookie session_info valide — refresh d'abord
      this.authService.refreshAccessToken().subscribe({
        next: t => this._doConnectToConversation(conversationId, t),
        error: () => { this.wsStatus$.next('error'); }
      });
    } else {
      console.warn('MessagingService: pas de token JWT — connexion WS annulée');
    }
  }

  private _doConnectToConversation(conversationId: string, token: string): void {
    this.currentConversationId = conversationId;
    const url = `${this.wsUrl}/ws/messaging/conversations/${conversationId}/?token=${encodeURIComponent(token)}`;
    this.wsStatus$.next('connecting');

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.wsStatus$.next('connected');
    };

    this.socket.onmessage = (event) => {
      try {
        const message: Message = JSON.parse(event.data);
        this.messages$.next(message);
      } catch (e) {
        console.error('MessagingService: erreur parsing message WS', e);
      }
    };

    this.socket.onerror = () => {
      this.wsStatus$.next('error');
    };

    this.socket.onclose = (event) => {
      this.wsStatus$.next('disconnected');
      // Reconnexion automatique si fermeture anormale
      if (event.code !== 1000 && this.currentConversationId === conversationId) {
        this.reconnectTimer = setTimeout(() => {
          this.connectToConversation(conversationId);
        }, 3000);
      }
    };
  }

  sendMessage(content: string): void {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ content }));
    } else {
      console.error('MessagingService: WebSocket non connecté — message non envoyé');
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.currentConversationId = null;
    if (this.socket) {
      this.socket.close(1000); // fermeture propre
      this.socket = null;
    }
    this.wsStatus$.next('disconnected');
  }

  ngOnDestroy(): void {
    this.disconnect();
    this.messages$.complete();
    this.wsStatus$.complete();
    this.unreadCount$.complete();
  }
}
