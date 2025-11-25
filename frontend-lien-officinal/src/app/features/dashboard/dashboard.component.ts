import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
// Drag & Drop Imports
import { DragDropModule, CdkDragDrop, moveItemInArray, transferArrayItem } from '@angular/cdk/drag-drop';

import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';

import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { HeaderComponent } from './components/header/header.component';
import { AdSpaceComponent } from '../../shared/ui/ad-space/ad-space.component';
import { AddLinkModalComponent } from '../../shared/ui/add-link-modal/add-link-modal.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule, 
    DragDropModule, // <--- IMPORTANT
    PinPadComponent, 
    SidebarComponent, 
    HeaderComponent, 
    AdSpaceComponent, 
    AddLinkModalComponent
  ],
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
  // Note : Pour le Drag&Drop, on travaille directement sur allCategories pour l'instant
  team: Collaborator[] = [];
  
  // États
  isEditMode = false; // <--- Le mode modification
  showPinPad = false;
  showAddModal = false;
  
  selectedCollaborator: Collaborator | null = null;
  activeSessionCollaborator: Collaborator | null = null; 

  ngOnInit() {
    this.loadCategories();
    this.loadTeam();
  }

  // --- API ---

  loadCategories() {
    this.http.get<any>('http://127.0.0.1:8000/api/categories/')
      .subscribe({
        next: (data) => {
          this.allCategories = Array.isArray(data) ? data : data.results || [];
        }
      });
  }

  loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (data: any) => this.team = Array.isArray(data) ? data : data.results || []
    });
  }

  // --- ACTIONS ---

  toggleEditMode() {
    this.isEditMode = !this.isEditMode;
    // Ici, on pourrait sauvegarder le nouvel ordre dans le backend si on quitte le mode édite
    if (!this.isEditMode) {
      console.log("Sauvegarde de l'ordre des catégories/liens...");
      // TODO: Appel API pour save order
    }
  }

  // Gère le Drag & Drop
  drop(event: CdkDragDrop<any[]>) {
    if (event.previousContainer === event.container) {
      // Déplacement dans la même colonne
      moveItemInArray(event.container.data, event.previousIndex, event.currentIndex);
    } else {
      // Déplacement d'une catégorie à l'autre
      transferArrayItem(
        event.previousContainer.data,
        event.container.data,
        event.previousIndex,
        event.currentIndex,
      );
    }
  }

  toggleFavorite(link: any, event: Event) {
    event.stopPropagation(); // Empêche d'ouvrir le lien
    // Simulation (il faudra une API pour persister ça)
    link.is_favorite = !link.is_favorite;
  }

  deleteLink(link: any, event: Event) {
    event.stopPropagation();
    if(confirm("Supprimer ce lien ?")) {
       this.http.delete(`http://127.0.0.1:8000/api/links/${link.id}/`).subscribe(() => this.loadCategories());
    }
  }

  openDetail(link: any) {
    if (this.isEditMode) return; // Pas de clic en mode édition
    console.log("Ouverture page détail pour :", link.titre);
    alert("Ouverture de la page de notes pour : " + link.titre);
    // Ici on ouvrira une Sidebar de droite ou une nouvelle page
  }

  // --- SESSION & SEARCH (Simplifiés pour l'exemple) ---
  onSearch(term: string) { /* ... code existant ... */ }
  openSession(collab: Collaborator) { this.selectedCollaborator = collab; this.showPinPad = true; }
  onPinEntered(code: string) { /* ... code existant ... */ }
  closeCollaboratorSession() { this.activeSessionCollaborator = null; }
  logout() { this.authService.logout(); }
  onLinkAdded(data: any) { /* ... code existant ... */ }
}