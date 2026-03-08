import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
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

export interface Attachment {
  id: string;
  file_name: string;
  file_size: number;
  file_type: string;
  created_at: string;
}

export interface Message {
  id: string;
  sender: CollaboratorMinimal;
  content: string;
  attachments: Attachment[];
  is_read_by: CollaboratorMinimal[];
  created_at: string;
}

// ── Service ───────────────────────────────────────────────────────────────────

@Injectable({
  providedIn: 'root'
})
export class MessagingService {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private apiUrl = `${environment.apiUrl}/api/messaging`;

  /** Compteur global de messages non lus — partagé avec la sidebar du dashboard. */
  readonly unreadCount$ = new BehaviorSubject<number>(0);

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

  /** Construit les headers avec X-Collaborator-Id si un collaborateur est actif. */
  private buildHeaders(): HttpHeaders {
    const collabId = this.getActiveCollaboratorId();
    return collabId
      ? new HttpHeaders({ 'X-Collaborator-Id': String(collabId) })
      : new HttpHeaders();
  }

  // ── Conversations ────────────────────────────────────────────────────────

  getConversations(): Observable<Conversation[]> {
    return this.http.get<Conversation[]>(
      `${this.apiUrl}/conversations/`,
      { headers: this.buildHeaders() }
    );
  }

  getConversation(id: string): Observable<Conversation> {
    return this.http.get<Conversation>(
      `${this.apiUrl}/conversations/${id}/`,
      { headers: this.buildHeaders() }
    );
  }

  createConversation(subject: string, participantIds: number[]): Observable<Conversation> {
    const collabId = this.getActiveCollaboratorId();
    return this.http.post<Conversation>(
      `${this.apiUrl}/conversations/`,
      {
        collaborator_id: collabId,
        subject,
        participant_ids: participantIds,
      },
      { headers: this.buildHeaders() }
    );
  }

  deleteConversation(id: string): Observable<void> {
    return this.http.delete<void>(
      `${this.apiUrl}/conversations/${id}/`,
      { headers: this.buildHeaders() }
    );
  }

  // ── Messages ─────────────────────────────────────────────────────────────

  getMessages(conversationId: string): Observable<Message[]> {
    return this.http.get<Message[]>(
      `${this.apiUrl}/conversations/${conversationId}/messages/`,
      { headers: this.buildHeaders() }
    );
  }

  sendMessage(conversationId: string, content: string): Observable<Message> {
    const collabId = this.getActiveCollaboratorId();
    return this.http.post<Message>(
      `${this.apiUrl}/conversations/${conversationId}/messages/`,
      { collaborator_id: collabId, content },
      { headers: this.buildHeaders() }
    );
  }

  markAsRead(conversationId: string): Observable<void> {
    return this.http.post<void>(
      `${this.apiUrl}/conversations/${conversationId}/mark-read/`,
      {},
      { headers: this.buildHeaders() }
    );
  }

  // ── Pièces jointes ───────────────────────────────────────────────────────

  uploadAttachment(messageId: string, file: File): Observable<Attachment> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<Attachment>(
      `${this.apiUrl}/messages/${messageId}/attachments/`,
      formData,
      { headers: this.buildHeaders() }
    );
  }

  downloadAttachment(attachmentId: string): Observable<Blob> {
    return this.http.get(
      `${this.apiUrl}/attachments/${attachmentId}/download/`,
      { headers: this.buildHeaders(), responseType: 'blob' }
    );
  }

  // ── Équipe ───────────────────────────────────────────────────────────────

  getTeamMembers(): Observable<Collaborator[]> {
    return this.http.get<Collaborator[]>(
      `${this.apiUrl}/team-members/`,
      { headers: this.buildHeaders() }
    );
  }
}
