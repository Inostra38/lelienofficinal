import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

// Modules pour le Drag & Drop
import { DragDropModule, CdkDragDrop, moveItemInArray, transferArrayItem } from '@angular/cdk/drag-drop';

// Services
import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';

// Composants Enfants
import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { HeaderComponent } from './components/header/header.component';
import { AdSpaceComponent } from '../../shared/ui/ad-space/ad-space.component';
import { AddLinkModalComponent } from '../../shared/ui/add-link-modal/add-link-modal.component';
import { CardDetailComponent } from './components/card-detail/card-detail.component';
import { CategoryAssignerModalComponent } from '../../shared/ui/category-assigner-modal/category-assigner-modal.component';

// --- DÉFINITION DES TYPES (Interfaces) ---
export interface ResourceItem {
  id: number;
  type: 'WEB' | 'PDF' | 'TEL' | 'MAIL';
  label: string;
  final_url: string;
  url: string;
  file: string | null;
}

export interface ResourceCard {
  id: number;
  titre: string;
  description_officielle: string;
  logo: string | null;
  type: 'OFFICIAL' | 'PARTNER' | 'PRIVATE';
  items?: ResourceItem[]; 
  partner: { id: number; nom: string; logo: string | null } | null;
  is_favorite: boolean;
  notes_perso: string;
}

export interface Category {
  id: number;
  nom: string;
  cards: ResourceCard[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    DragDropModule, 
    PinPadComponent, 
    SidebarComponent, 
    HeaderComponent, 
    AdSpaceComponent, 
    AddLinkModalComponent,
    CardDetailComponent,
    CategoryAssignerModalComponent 
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit { // 👈 DÉBUT DE LA CLASSE
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);

  @ViewChild(PinPadComponent) pinPad!: PinPadComponent;

  // --- DONNÉES ---
  allCategories: Category[] = [];       
  displayedCategories: Category[] = []; 
  team: Collaborator[] = [];            
  libraryItems: any[] = []; 
  
  // --- ÉTATS ---
  viewMode: 'COMPACT' | 'LARGE' | 'TABLE' = 'COMPACT'; 
  isEditMode = false;   
  isSearching = false;  
  showPinPad = false;
  showAddModal = false; 
  
  selectedCollaborator: Collaborator | null = null;
  activeSessionCollaborator: Collaborator | null = null;
  openedCard: ResourceCard | null = null;
  selectedCardToAssign: ResourceCard | null = null; 

  ngOnInit() {
    this.loadCategories();
    this.loadTeam();
    this.loadLibrary();
  }

  // ============================================================
  // 1. CHARGEMENT DES DONNÉES
  // ============================================================

  loadCategories() {
    const timestamp = new Date().getTime(); 
    
    this.http.get<any>(`http://127.0.0.1:8000/api/categories/?t=${timestamp}`)
      .subscribe({
        next: (data) => {
          const rawData = Array.isArray(data) ? data : data.results || [];
          
          this.allCategories = rawData.map((cat: Category) => ({
            ...cat,
            cards: (cat.cards || []).map(card => ({
                ...card,
                items: card.items || [] 
            }))
          }));
          this.updateDisplay();
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

  loadLibrary() {
      this.http.get<any[]>('http://127.0.0.1:8000/api/catalog/cards/')
      .subscribe({
        next: (data) => this.libraryItems = data,
        error: (err) => console.error('Erreur catalogue', err)
      });
  }

  private updateDisplay() {
    this.displayedCategories = JSON.parse(JSON.stringify(this.allCategories));
  }

  // ============================================================
  // 2. GESTION DES VUES & RECHERCHE
  // ============================================================

  setViewMode(mode: 'COMPACT' | 'LARGE' | 'TABLE') {
    this.viewMode = mode;
  }

  onSearch(term: string) {
    term = term.toLowerCase().trim();
    this.isSearching = !!term;

    if (!term) {
      this.updateDisplay();
      return;
    }

    this.displayedCategories = this.allCategories.map(cat => {
      const matchingCards = cat.cards.filter(card => {
        const titleMatch = (card.titre || '').toLowerCase().includes(term);
        const partnerMatch = (card.partner?.nom || '').toLowerCase().includes(term);
        const itemMatch = (card.items || []).some(item => (item.label || '').toLowerCase().includes(term));
        
        return titleMatch || partnerMatch || itemMatch;
      });

      return { ...cat, cards: matchingCards };
    }).filter(cat => cat.cards.length > 0);
  }

  // ============================================================
  // 3. ACTIONS
  // ============================================================

  toggleEditMode() {
    this.isEditMode = !this.isEditMode;
  }

  drop(event: CdkDragDrop<any[]>) {
    if (event.previousContainer === event.container) {
      moveItemInArray(event.container.data, event.previousIndex, event.currentIndex);
    } else {
      transferArrayItem(
        event.previousContainer.data,
        event.container.data,
        event.previousIndex,
        event.currentIndex,
      );
    }
  }

  hideOrDeleteCard(card: ResourceCard, event: Event) { 
    event.stopPropagation();
    
    // 1. Suppression (si carte privée)
    if(card.type === 'PRIVATE') {
       if(confirm(`Voulez-vous vraiment SUPPRIMER votre carte privée "${card.titre}" ? Cette action est irréversible.`)) {
           this.http.delete(`http://127.0.0.1:8000/api/cards/${card.id}/`).subscribe({
               next: () => {
                   this.loadCategories();
               },
               error: (err) => console.error("Erreur suppression", err)
           });
       }
       return;
    }

    // 2. Masquage (si carte officielle/partenaire)
    if(confirm(`Voulez-vous masquer la carte "${card.titre}" de votre tableau de bord ?`)) {
        this.http.post(`http://127.0.0.1:8000/api/cards/${card.id}/toggle-visibility/`, {}).subscribe({
            next: () => this.loadCategories(),
            error: (err) => console.error("Erreur masquage", err)
        });
    }
  }

  toggleFavorite(card: ResourceCard, event: Event) {
    event.stopPropagation();
    card.is_favorite = !card.is_favorite;
  }

  openDetail(card: ResourceCard, event: Event) {
    event.preventDefault(); 
    event.stopPropagation();
    if (this.isEditMode) return; 
    this.openedCard = card; 
  }

  closeDetail() {
    this.openedCard = null;
  }
  
  handleCardSelection(card: ResourceCard) {
    this.showAddModal = false; 
    this.selectedCardToAssign = card; 
  }

  assignCategory(categoryId: number) { 
    if (!this.selectedCardToAssign) return;

    const cardId = this.selectedCardToAssign.id;
    const payload = { category: categoryId };
    
    this.http.patch(`http://127.0.0.1:8000/api/cards/${cardId}/assign-category/`, payload)
      .subscribe({
        next: () => {
          this.selectedCardToAssign = null;
          
          // 🔥 FIX CRITIQUE : Petit délai pour laisser la base de données s'actualiser
          setTimeout(() => {
            this.loadCategories(); // Recharge après 100ms
            alert(`✅ Ressource classée et ajoutée !`);
          }, 100); 

        },
        error: (err) => {
          console.error("❌ ERREUR ASSIGNATION :", err.error);
          alert(`Erreur d'assignation : ${err.error?.category?.[0] || 'Vérifiez la console.'}`);
          this.selectedCardToAssign = null; 
        }
      });
}

  // --- GESTION ÉQUIPE & AUTH ---

  openSession(collab: Collaborator) {
    this.selectedCollaborator = collab;
    this.showPinPad = true;
  }

  onPinEntered(code: string) {
    if (!this.selectedCollaborator) return;
    this.collaboratorService.verifyPin(this.selectedCollaborator.id, code)
      .subscribe({
        next: () => {
          this.activeSessionCollaborator = this.selectedCollaborator;
          this.showPinPad = false;
        },
        error: () => this.pinPad.triggerError()
      });
  }

  closeCollaboratorSession() {
    this.activeSessionCollaborator = null; 
  }

  logout() {
    this.authService.logout();
  }

  // --- AJOUT DE LIEN PERSONNEL ---

  onLinkAdded(data: any) {
    
    // --- VALIDATION INITIALE ---
    if (!data.title || !data.category) {
        alert("Le titre et la catégorie sont obligatoires.");
        return;
    }
    if (this.allCategories.length === 0) {
        alert("Erreur critique : Aucune catégorie n'est chargée. Rechargez la page.");
        return;
    }

    // 1. Détermination de l'ID de Catégorie (S'assurer d'avoir la valeur)
    let finalCategoryId = data.category;
    
    if (data.type === 'WEB' && !data.url) { alert("L'URL est obligatoire pour un lien Web."); return; }
    if (data.type === 'FILE' && !data.file) { alert("Le fichier est obligatoire."); return; }
    
    // --- CONSTRUCTION DU PAYLOAD (FormData) ---
    const formData = new FormData();
    formData.append('titre', data.title);
    
    // 💡 FIX CRITIQUE : Conversion explicite en chaîne pour la FK
    formData.append('category', String(finalCategoryId)); 

    formData.append('type', data.type);

    if (data.type === 'WEB') {
      formData.append('url', data.url);
    } else {
      formData.append('document', data.file);
    }

    // --- APPEL API ---
    this.http.post('http://127.0.0.1:8000/api/cards/', formData).subscribe({
      next: () => {
        alert('✅ Ressource ajoutée !');
        this.showAddModal = false;
        this.loadCategories(); // Rafraîchissement
      },
      error: (err) => {
        console.error('❌ ERREUR POST DJANGO:', err.error);
        // Affichage de l'erreur spécifique de validation Django (pour identifier le champ manquant)
        const errorDetail = err.error?.category?.[0] || err.error?.detail || JSON.stringify(err.error);
        alert(`Erreur d'ajout (400) : ${errorDetail}`);
      }
    });
  }
} // 👈 FIN DE LA CLASSE