import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type MemberRole = 'Titulaire' | 'Adjoint' | 'Préparateur' | 'Étudiant' | 'Apprenti';
export type MemberCivility = 'M.' | 'Mme' | 'Autre';

export interface Collaborator {
  id?: number;
  civility: MemberCivility;
  first_name: string;
  last_name: string;
  role: MemberRole;
  color: string;
  pin?: string;
  is_active?: boolean;
  created_at?: string;
}

export interface CollaboratorCreate extends Collaborator {
  pin: string;
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
}