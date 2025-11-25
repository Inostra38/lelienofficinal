import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface Collaborator {
  id: number;
  first_name: string;
  last_name: string;
  role: string;
}

@Injectable({
  providedIn: 'root'
})
export class CollaboratorService {
  private http = inject(HttpClient);
  // L'URL de ton API (maintenant qu'elle marche !)
  private apiUrl = 'http://127.0.0.1:8000/api/team/';

  // Récupérer l'équipe
  getTeam(): Observable<Collaborator[]> {
    return this.http.get<Collaborator[]>(this.apiUrl);
  }

  // Vérifier le PIN
  verifyPin(collaboratorId: number, pin: string): Observable<any> {
    return this.http.post<any>(`${this.apiUrl}verify-pin/`, {
      collaborator_id: collaboratorId,
      pin_code: pin
    });
  }
}