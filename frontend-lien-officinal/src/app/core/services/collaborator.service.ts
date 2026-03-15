import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
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
  archived_at?: string | null;
  created_at?: string;
  contract_type?: string;
  weekly_hours?: number;
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

@Injectable({
  providedIn: 'root'
})
export class CollaboratorService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/team`;

  getTeam(includeArchived = false): Observable<Collaborator[]> {
    const url = includeArchived
      ? `${this.apiUrl}/?include_archived=true`
      : `${this.apiUrl}/`;
    return this.http.get<Collaborator[]>(url);
  }

  reactivate(id: number): Observable<Collaborator> {
    return this.http.patch<Collaborator>(`${this.apiUrl}/${id}/reactivate/`, {});
  }

  createCollaborator(data: CollaboratorCreate): Observable<Collaborator> {
    return this.http.post<Collaborator>(`${this.apiUrl}/`, data);
  }

  updateCollaborator(id: number, data: Partial<Collaborator>): Observable<Collaborator> {
    return this.http.patch<Collaborator>(`${this.apiUrl}/${id}/`, data);
  }

  deleteCollaborator(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}/`);
  }

  verifyPin(collaboratorId: number, pin: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}/verify-pin/`, {
      collaborator_id: collaboratorId,
      pin_code: pin
    });
  }

  reorderCollaborators(order: number[]): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/reorder/`, { order });
  }
}
