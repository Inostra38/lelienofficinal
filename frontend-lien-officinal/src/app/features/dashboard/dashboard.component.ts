import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

// Services
import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';

// Composants Enfants
import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { HeaderComponent } from './components/header/header.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, PinPadComponent, SidebarComponent, HeaderComponent],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);

  @ViewChild(PinPadComponent) pinPad!: PinPadComponent;

  // Données
  allCategories: any[] = [];
  displayedCategories: any[] = [];
  team: Collaborator[] = [];
  
  // États
  showPinPad = false;
  selectedCollaborator: Collaborator | null = null;
  activeSessionCollaborator: Collaborator | null = null; 

  ngOnInit() {
    this.loadCategories();
    this.loadTeam();
  }

  // --- CHARGEMENT DES DONNÉES ---

  loadCategories() {
    this.http.get<any>('http://127.0.0.1:8000/api/categories/')
      .subscribe({
        next: (data) => {
          this.allCategories = Array.isArray(data) ? data : data.results || [];
          this.displayedCategories = this.allCategories;
        },
        error: (err) => console.error('Erreur chargement catégories', err)
      });
  }

  loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (data: any) => {
        this.team = Array.isArray(data) ? data : data.results || [];
      },
      error: (err) => console.error('Erreur chargement équipe', err)
    });
  }

  // --- RECHERCHE ---

  onSearch(term: string) {
    term = term.toLowerCase();
    if (!term) {
      this.displayedCategories = this.allCategories;
      return;
    }

    this.displayedCategories = this.allCategories.map(cat => {
      const matchingLinks = cat.links.filter((link: any) => 
        link.titre.toLowerCase().includes(term) || 
        (link.partner?.nom && link.partner.nom.toLowerCase().includes(term))
      );
      return { ...cat, links: matchingLinks };
    }).filter(cat => cat.links.length > 0);
  }

  // --- GESTION PIN & SESSION ---

  openSession(collab: Collaborator) {
    this.selectedCollaborator = collab;
    this.showPinPad = true;
  }

  onPinEntered(code: string) {
    if (!this.selectedCollaborator) return;

    this.collaboratorService.verifyPin(this.selectedCollaborator.id, code)
      .subscribe({
        next: () => {
          // Succès : On active la session de "Julie"
          this.activeSessionCollaborator = this.selectedCollaborator;
          this.showPinPad = false;
        },
        error: () => {
          // Erreur : On fait vibrer le PinPad
          this.pinPad.triggerError();
        }
      });
  }

  // 👇 C'EST ICI LE CHANGEMENT IMPORTANT 👇
  
  // Appelé quand on clique sur la croix rouge dans la sidebar
  closeCollaboratorSession() {
    console.log("Fermeture de la session utilisateur locale.");
    this.activeSessionCollaborator = null; 
    // On ne retourne PAS au login, on reste sur le dashboard avec la liste "Qui êtes-vous ?"
  }

  // Appelé seulement si on veut sortir totalement de l'application (bouton caché pour l'instant)
  globalLogout() {
    this.authService.logout();
  }
}