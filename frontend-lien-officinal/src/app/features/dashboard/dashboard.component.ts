import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, PinPadComponent], // <-- On importe le PinPad
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);

  @ViewChild(PinPadComponent) pinPad!: PinPadComponent;

  categories: any[] = [];
  team: Collaborator[] = [];
  
  showPinPad = false;
  selectedCollaborator: Collaborator | null = null;
  activeSessionCollaborator: Collaborator | null = null; // Celui qui est connecté

  ngOnInit() {
    this.loadCategories();
    this.loadTeam();
  }

  loadCategories() {
    this.http.get<any>('http://127.0.0.1:8000/api/categories/')
      .subscribe({
        next: (data) => this.categories = Array.isArray(data) ? data : data.results || []
      });
  }

  loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (data: any) => {
        // Gestion de la pagination Django si nécessaire
        this.team = Array.isArray(data) ? data : data.results || [];
      },
      error: (err) => console.error('Erreur équipe', err)
    });
  }

  // Ouvre le PinPad
  openSession(collab: Collaborator) {
    this.selectedCollaborator = collab;
    this.showPinPad = true;
  }

  // Vérifie le code tapé
  onPinEntered(code: string) {
    if (!this.selectedCollaborator) return;

    this.collaboratorService.verifyPin(this.selectedCollaborator.id, code)
      .subscribe({
        next: () => {
          // Succès !
          this.activeSessionCollaborator = this.selectedCollaborator;
          this.showPinPad = false;
          alert(`✅ Session ouverte pour ${this.selectedCollaborator?.first_name}`);
        },
        error: () => {
          // Erreur !
          this.pinPad.triggerError();
        }
      });
  }

  logout() {
    this.authService.logout();
  }
}