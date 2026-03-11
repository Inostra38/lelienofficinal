import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type MemberRole = 'Titulaire' | 'Adjoint' | 'Préparateur' | 'Étudiant' | 'Apprenti';
export type MemberCivility = 'M.' | 'Mme' | 'Autre';

export interface CollaboratorPermissions {
  can_manage_account: boolean;
  can_manage_team: boolean;
  can_manage_planning: boolean;
  can_manage_quality: boolean;
}

export interface Collaborator extends CollaboratorPermissions {
  id?: number;
  civility: MemberCivility;
  first_name: string;
  last_name: string;
  role: MemberRole;
  email?: string;
  color: string;
  pin?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface CollaboratorCreate {
  civility: MemberCivility;
  first_name: string;
  last_name: string;
  role: MemberRole;
  email?: string;
  color: string;
  pin: string;
  can_manage_account?: boolean;
  can_manage_team?: boolean;
  can_manage_planning?: boolean;
  can_manage_quality?: boolean;
}

export interface SensitivePayload {
  confirmation_pin?: string;
  confirmation_password?: string;
}

@Injectable({
  providedIn: 'root'
})
export class CollaboratorService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/team`;

  getTeam(): Observable<Collaborator[]> {
    return this.http.get<Collaborator[]>(`${this.apiUrl}/`);
  }

  createCollaborator(data: CollaboratorCreate & SensitivePayload): Observable<Collaborator> {
    return this.http.post<Collaborator>(`${this.apiUrl}/`, data);
  }

  updateCollaborator(id: number, data: Partial<Collaborator>): Observable<Collaborator> {
    return this.http.patch<Collaborator>(`${this.apiUrl}/${id}/`, data);
  }

  updatePermissions(id: number, permissions: Partial<CollaboratorPermissions>, confirmation: SensitivePayload): Observable<Collaborator> {
    return this.http.patch<Collaborator>(`${this.apiUrl}/${id}/permissions/`, { ...permissions, ...confirmation });
  }

  deleteCollaborator(id: number, confirmation: SensitivePayload): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}/`, {
      body: confirmation,
      headers: new HttpHeaders({ 'Content-Type': 'application/json' })
    });
  }

  verifyPin(collaboratorId: number, pin: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/verify-pin/`, {
      collaborator_id: collaboratorId,
      pin_code: pin
    });
  }

  verifyTeamPin(pin: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/verify-team-pin/`, { confirmation_pin: pin });
  }
}
