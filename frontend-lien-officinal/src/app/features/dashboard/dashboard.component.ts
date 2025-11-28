import { Component, inject, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';

import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';

import { PinPadComponent } from '../../shared/ui/pin-pad/pin-pad.component';
import { SidebarComponent } from './components/sidebar/sidebar.component';
import { HeaderComponent } from './components/header/header.component';
import { AdSpaceComponent } from '../../shared/ui/ad-space/ad-space.component';
import { AddLinkModalComponent } from '../../shared/ui/add-link-modal/add-link-modal.component';
import { CardDetailComponent } from './components/card-detail/card-detail.component';
import { CategoryAssignerModalComponent } from '../../shared/ui/category-assigner-modal/category-assigner-modal.component';
import { MoveCardModalComponent } from '../../shared/ui/move-card-modal/move-card-modal.component';

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
    PinPadComponent,
    SidebarComponent,
    HeaderComponent,
    CardDetailComponent,
    CategoryAssignerModalComponent,
    AddLinkModalComponent,
    MoveCardModalComponent
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private http = inject(HttpClient);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);

  showOnlyFavorites = false;

  @ViewChild(PinPadComponent) pinPad!: PinPadComponent;

  // --- DONNÉES ---
  allCategories: Category[] = [];
  displayedCategories: Category[] = [];
  team: Collaborator[] = [];
  libraryItems: any[] = [];

  // --- ÉTATS ---
  viewMode: 'COMPACT' | 'LARGE' | 'TABLE' | 'ICON' = 'COMPACT';
  isEditMode = false;
  isSearching = false;
  showPinPad = false;
  showAddModal = false;

  selectedCollaborator: Collaborator | null = null;
  activeSessionCollaborator: Collaborator | null = null;
  openedCard: ResourceCard | null = null;
  selectedCardToAssign: ResourceCard | null = null;

  cardToMove: ResourceCard | null = null;
  currentCategoryIdForMove: number | null = null;

  editingCategoryId: number | null = null;
  editingCategoryName: string = '';

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

  refreshData() {
    console.log('🔄 Rafraîchissement des données...');
    this.loadCategories();
    this.loadTeam();
    this.loadLibrary();
  }
private updateDisplay() {
  const rawData: Category[] = JSON.parse(JSON.stringify(this.allCategories));

  this.displayedCategories = rawData.map(category => {
    const nativeCards = category.cards || [];
    const adoptedCards = category.adopted_cards || [];
    let mergedCards = [...nativeCards, ...adoptedCards];
    
    // ✅ Filtrer par favoris si activé
    if (this.showOnlyFavorites) {
      mergedCards = mergedCards.filter(card => card.is_favorite);
    }
    
    mergedCards.sort((a, b) => a.titre.localeCompare(b.titre));

    return {
      ...category,
      cards: mergedCards
    };
  }).filter(cat => cat.cards.length > 0); // ✅ Ne montrer que les catégories avec des cartes
}

  // ============================================================
  // 2. GESTION DES VUES & RECHERCHE
  // ============================================================

  toggleFavoritesFilter() {
    this.showOnlyFavorites = !this.showOnlyFavorites;
    this.updateDisplay();
  }

  setViewMode(mode: 'COMPACT' | 'LARGE' | 'TABLE' | 'ICON') {
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
        // 1. Recherche dans le titre
        const titleMatch = (card.titre || '').toLowerCase().includes(term);

        // 2. Recherche dans la description
        const descMatch = (card.description_officielle || '').toLowerCase().includes(term);

        // 3. Recherche dans le nom du partenaire
        const partnerMatch = (card.partner?.nom || '').toLowerCase().includes(term);

        // 4. Recherche dans les notes
        const noteCourtMatch = (card.note_courte || '').toLowerCase().includes(term);
        const noteLongueMatch = (card.note_longue || '').toLowerCase().includes(term);

        // 5. Recherche dans les items (label + URL)
        const itemMatch = (card.items || []).some(item => {
          const labelMatch = (item.label || '').toLowerCase().includes(term);
          const urlMatch = (item.url || '').toLowerCase().includes(term);
          return labelMatch || urlMatch;
        });

        return titleMatch || descMatch || partnerMatch || noteCourtMatch || noteLongueMatch || itemMatch;
      });

      return { ...cat, cards: matchingCards };
    }).filter(cat => cat.cards.length > 0);

    // ✅ BONUS : Afficher aussi le nom des catégories qui matchent
    // (même si elles n'ont pas de cartes matchantes)
    const categoryNameMatches = this.allCategories.filter(cat =>
      (cat.nom || '').toLowerCase().includes(term)
    );

    // Fusionner avec les résultats existants
    categoryNameMatches.forEach(catMatch => {
      if (!this.displayedCategories.find(c => c.id === catMatch.id)) {
        this.displayedCategories.push({ ...catMatch, cards: catMatch.cards || [] });
      }
    });
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
          // Silencieux
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

  openMoveCardModal(card: ResourceCard, categoryId: number, event: Event) {
    event.stopPropagation();
    this.cardToMove = card;
    this.currentCategoryIdForMove = categoryId;
  }

  moveCard(newCategoryId: number) {
    if (!this.cardToMove) return;

    const card = this.cardToMove;

    if (card.type === 'PRIVATE') {
      const formData = new FormData();
      formData.append('category', newCategoryId.toString());

      this.http.patch(`http://127.0.0.1:8000/api/cards/${card.id}/`, formData)
        .subscribe({
          next: () => {
            this.cardToMove = null;
            this.currentCategoryIdForMove = null;
            this.loadCategories();
          },
          error: (err) => {
            console.error('Erreur déplacement carte', err);
            alert("Erreur lors du déplacement.");
          }
        });
    } else {
      this.http.patch(`http://127.0.0.1:8000/api/cards/${card.id}/assign-category/`,
        { category: newCategoryId }
      ).subscribe({
        next: () => {
          this.cardToMove = null;
          this.currentCategoryIdForMove = null;
          this.loadCategories();
        },
        error: (err) => {
          console.error('Erreur déplacement carte', err);
          alert("Erreur lors du déplacement.");
        }
      });
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
        
        // ✅ MISE À JOUR DANS allCategories
        this.allCategories.forEach(cat => {
          // Chercher dans les cartes natives
          const cardIndex = (cat.cards || []).findIndex(c => c.id === card.id);
          if (cardIndex !== -1) {
            cat.cards[cardIndex].is_favorite = response.is_favorite;
          }

          // Chercher dans les cartes adoptées
          if (cat.adopted_cards) {
            const adoptedIndex = cat.adopted_cards.findIndex(c => c.id === card.id);
            if (adoptedIndex !== -1) {
              cat.adopted_cards[adoptedIndex].is_favorite = response.is_favorite;
            }
          }
        });

        // ✅ FORCER LE REFRESH DE L'AFFICHAGE
        this.updateDisplay();
      },
      error: (err) => {
        // Rollback en cas d'erreur
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

  closeDetailAndRefresh() {
    this.openedCard = null;
    // ✅ Ne PLUS recharger depuis le serveur
    // La mise à jour locale suffit
  }

  onCardUpdated(updatedCard: any) {
    console.log('🔄 Mise à jour locale de la carte:', updatedCard.id);

    // 1. Mettre à jour la carte actuellement ouverte
    if (this.openedCard && this.openedCard.id === updatedCard.id) {
      Object.assign(this.openedCard, updatedCard);
    }

    // 2. Mettre à jour dans allCategories
    let found = false;

    this.allCategories.forEach(cat => {
      // Chercher dans les cartes natives
      const cardIndex = (cat.cards || []).findIndex(c => c.id === updatedCard.id);
      if (cardIndex !== -1) {
        cat.cards[cardIndex] = { ...cat.cards[cardIndex], ...updatedCard };
        found = true;
      }

      // Chercher dans les cartes adoptées
      if (cat.adopted_cards) {
        const adoptedIndex = cat.adopted_cards.findIndex(c => c.id === updatedCard.id);
        if (adoptedIndex !== -1) {
          cat.adopted_cards[adoptedIndex] = { ...cat.adopted_cards[adoptedIndex], ...updatedCard };
          found = true;
        }
      }
    });

    // 3. Forcer la mise à jour de l'affichage
    if (found) {
      this.updateDisplay();
    }
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

  // ============================================================
  // 9. BADGES
  // ============================================================

  getBadgeClass(cardType: string): string {
    switch (cardType) {
      case 'PRIVATE': return 'badge-private';
      case 'OFFICIAL': return 'badge-official';
      case 'PARTNER': return 'badge-partner';
      default: return '';
    }
  }

  getBadgeLabel(cardType: string): string {
    switch (cardType) {
      case 'PRIVATE': return 'Privée';
      case 'OFFICIAL': return 'Validé';
      case 'PARTNER': return 'Officiel';
      default: return '';
    }
  }
}