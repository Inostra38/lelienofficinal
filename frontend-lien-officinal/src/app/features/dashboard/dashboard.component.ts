import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

import { DragDropModule, CdkDragDrop, moveItemInArray, transferArrayItem } from '@angular/cdk/drag-drop';

import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { InactivityAdService } from '../../core/services/inactivity-ad.service'; // ✅ AJOUT

import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { HeaderComponent } from './components/header/header.component';
import { AdSpaceComponent } from '../../shared/ui/ad-space/ad-space.component';
import { AddLinkModalComponent } from '../../shared/ui/add-link-modal/add-link-modal.component';
import { CardDetailComponent } from './components/card-detail/card-detail.component';
import { CategoryAssignerModalComponent } from '../../shared/ui/category-assigner-modal/category-assigner-modal.component';
import { InactivityAdOverlayComponent } from '../../shared/ui/inactivity-ad-overlay/inactivity-ad-overlay.component'; // ✅ AJOUT

// --- INTERFACES ---
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
  note_courte: string;
  note_longue: string;
}

export interface Category {
  id: number;
  nom: string;
  icon_slug: string;
  cards: ResourceCard[];
  adopted_cards?: ResourceCard[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    DragDropModule,
    PinPadComponent,
    SidebarComponent,
    HeaderComponent,
    AdSpaceComponent,
    AddLinkModalComponent,
    CardDetailComponent,
    CategoryAssignerModalComponent,
    InactivityAdOverlayComponent // ✅ AJOUT
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);
  private inactivityAdService = inject(InactivityAdService); // ✅ AJOUT

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

  // --- RENOMMAGE CATÉGORIE ---
  editingCategoryId: number | null = null;
  editingCategoryName: string = '';

  ngOnInit() {
    this.loadCategories();
    this.loadTeam();
    this.loadLibrary();
    this.loadInactivityAd(); // ✅ AJOUT
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
            })),
            adopted_cards: (cat.adopted_cards || []).map(card => ({
              ...card,
              items: card.items || []
            }))
          }));

          this.updateDisplay();
        },
        error: (err) => console.error('Erreur chargement catégories', err)
      });
  }

  // ✅ NOUVEAU : Méthode de rafraîchissement
  refreshData() {
    console.log('🔄 Rafraîchissement des données...');
    this.loadCategories();
    this.loadTeam();
    this.loadLibrary();
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

  // ✅ NOUVEAU : Charger une pub d'inactivité
  loadInactivityAd() {
    this.http.get<any>('http://127.0.0.1:8000/api/ads/inactivity/')
      .subscribe({
        next: (ad) => {
          console.log('📺 Publicité chargée:', ad);
          this.inactivityAdService.loadAd(ad);
        },
        error: (err) => {
          console.warn('⚠️ Pas de publicité disponible', err);
        }
      });
  }

  private updateDisplay() {
    const rawData: Category[] = JSON.parse(JSON.stringify(this.allCategories));

    this.displayedCategories = rawData.map(category => {
      const nativeCards = category.cards || [];
      const adoptedCards = category.adopted_cards || [];
      const mergedCards = [...nativeCards, ...adoptedCards];
      mergedCards.sort((a, b) => a.titre.localeCompare(b.titre));

      return {
        ...category,
        cards: mergedCards
      };
    });
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
      const allCards = [...(cat.cards || []), ...(cat.adopted_cards || [])];

      const matchingCards = allCards.filter(card => {
        const titleMatch = (card.titre || '').toLowerCase().includes(term);
        const partnerMatch = (card.partner?.nom || '').toLowerCase().includes(term);
        const itemMatch = (card.items || []).some(item => (item.label || '').toLowerCase().includes(term));

        return titleMatch || partnerMatch || itemMatch;
      });

      return { ...cat, cards: matchingCards };
    }).filter(cat => cat.cards.length > 0);
  }

  // ============================================================
  // 3. ACTIONS SUR LES CATÉGORIES
  // ============================================================

  deleteCategory(category: Category) {
    const cardsCount = category.cards?.length || 0;
    const message = cardsCount > 0
      ? `Voulez-vous vraiment supprimer la catégorie "${category.nom}" et ses ${cardsCount} carte(s) ?`
      : `Voulez-vous vraiment supprimer la catégorie "${category.nom}" ?`;

    if (confirm(message)) {
      this.http.delete(`http://127.0.0.1:8000/api/categories/${category.id}/`)
        .subscribe({
          next: () => {
            this.loadCategories();
          },
          error: (err) => {
            console.error('Erreur suppression catégorie', err);
            alert("Erreur lors de la suppression.");
          }
        });
    }
  }

  // ============================================================
  // 4. RENOMMAGE DE CATÉGORIE
  // ============================================================

  startRename(category: Category) {
    this.editingCategoryId = category.id;
    this.editingCategoryName = category.nom;
  }

  cancelRename() {
    this.editingCategoryId = null;
    this.editingCategoryName = '';
  }

  saveRename(category: Category) {
    if (!this.editingCategoryName.trim()) {
      alert("Le nom ne peut pas être vide.");
      return;
    }

    this.http.patch(`http://127.0.0.1:8000/api/categories/${category.id}/`, {
      nom: this.editingCategoryName.trim()
    }).subscribe({
      next: () => {
        this.editingCategoryId = null;
        this.editingCategoryName = '';
        this.loadCategories();
      },
      error: (err) => {
        console.error('Erreur renommage', err);
        alert(err.error?.nom?.[0] || "Erreur lors du renommage.");
      }
    });
  }

  // ============================================================
  // 5. RÉORDONNANCEMENT DES CATÉGORIES
  // ============================================================

  isFirstCategory(category: Category): boolean {
    return this.displayedCategories.indexOf(category) === 0;
  }

  isLastCategory(category: Category): boolean {
    return this.displayedCategories.indexOf(category) === this.displayedCategories.length - 1;
  }

  moveCategoryUp(category: Category) {
    const index = this.displayedCategories.indexOf(category);
    if (index <= 0) return;

    [this.displayedCategories[index - 1], this.displayedCategories[index]] =
      [this.displayedCategories[index], this.displayedCategories[index - 1]];

    const allIndex = this.allCategories.findIndex(c => c.id === category.id);
    if (allIndex > 0) {
      [this.allCategories[allIndex - 1], this.allCategories[allIndex]] =
        [this.allCategories[allIndex], this.allCategories[allIndex - 1]];
    }

    this.saveOrder();
  }

  moveCategoryDown(category: Category) {
    const index = this.displayedCategories.indexOf(category);
    if (index >= this.displayedCategories.length - 1) return;

    [this.displayedCategories[index], this.displayedCategories[index + 1]] =
      [this.displayedCategories[index + 1], this.displayedCategories[index]];

    const allIndex = this.allCategories.findIndex(c => c.id === category.id);
    if (allIndex < this.allCategories.length - 1) {
      [this.allCategories[allIndex], this.allCategories[allIndex + 1]] =
        [this.allCategories[allIndex + 1], this.allCategories[allIndex]];
    }

    this.saveOrder();
  }

  private saveOrder() {
    const order = this.displayedCategories.map(cat => cat.id);

    this.http.post('http://127.0.0.1:8000/api/categories/reorder/', { order })
      .subscribe({
        next: () => {
          // Silencieux - pas besoin de feedback
        },
        error: (err) => {
          console.error('Erreur sauvegarde ordre', err);
          this.loadCategories();
        }
      });
  }

  // ============================================================
  // 6. ACTIONS SUR LES CARTES
  // ============================================================

  toggleEditMode() {
    this.isEditMode = !this.isEditMode;
    if (!this.isEditMode) {
      this.cancelRename();
    }
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

    if (card.type === 'PRIVATE') {
      if (confirm(`Voulez-vous vraiment SUPPRIMER votre carte privée "${card.titre}" ?`)) {
        this.http.delete(`http://127.0.0.1:8000/api/cards/${card.id}/`).subscribe({
          next: () => this.loadCategories(),
          error: (err) => console.error("Erreur suppression", err)
        });
      }
      return;
    }

    if (confirm(`Voulez-vous masquer la carte "${card.titre}" de votre tableau de bord ?`)) {
      this.http.post(`http://127.0.0.1:8000/api/cards/${card.id}/toggle-visibility/`, {}).subscribe({
        next: () => this.loadCategories(),
        error: (err) => console.error("Erreur masquage", err)
      });
    }
  }

  toggleFavorite(card: ResourceCard, event: Event) {
    event.stopPropagation();

    card.is_favorite = !card.is_favorite;

    this.http.post(`http://127.0.0.1:8000/api/cards/${card.id}/toggle-favorite/`, {})
      .subscribe({
        next: (response: any) => {
          card.is_favorite = response.is_favorite;
        },
        error: (err) => {
          card.is_favorite = !card.is_favorite;
          console.error('Erreur toggle favori', err);
        }
      });
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
          this.loadCategories();
          alert(`✅ Ressource classée et ajoutée !`);
        },
        error: (err) => {
          console.error("❌ ERREUR ASSIGNATION :", err.error);
          alert(`Erreur d'assignation : ${err.error?.category?.[0] || 'Vérifiez la console.'}`);
          this.selectedCardToAssign = null;
        }
      });
  }

  // ============================================================
  // 7. GESTION ÉQUIPE & AUTH
  // ============================================================

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

  // ============================================================
  // 8. AJOUT DE LIEN PERSONNEL
  // ============================================================

  onLinkAdded(data: any) {
    if (this.allCategories.length === 0) {
      alert("Aucune catégorie disponible. Créez d'abord une catégorie.");
      return;
    }

    let finalCategoryId = data.category;
    if (!finalCategoryId) {
      finalCategoryId = this.allCategories[0].id;
    }

    const formData = new FormData();
    formData.append('titre', data.title);
    formData.append('category', finalCategoryId);

    if (data.type === 'WEB') {
      formData.append('type', 'WEB');
      formData.append('url', data.url);
    } else {
      formData.append('type', 'PDF');
      formData.append('document', data.file);
    }

    this.http.post('http://127.0.0.1:8000/api/cards/', formData).subscribe({
      next: () => {
        alert('✅ Ressource ajoutée !');
        this.showAddModal = false;
        this.loadCategories();
      },
      error: (err) => {
        console.error('❌ Erreur POST :', err);
        alert("Erreur lors de l'ajout d'une ressource.");
      }
    });
  }
}