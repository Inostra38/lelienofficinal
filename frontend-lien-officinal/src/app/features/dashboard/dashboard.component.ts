import { Component, inject, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { PharmacyService } from '../../core/services/pharmacy.service';
import { ToastService } from '../../core/services/toast.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { AuthService } from '../../core/auth/auth.service';
import { DashboardApiService } from './services/dashboard-api.service';
import { DashboardDisplayService } from './services/dashboard-display.service';

import { HeaderComponent } from './components/header/header.component';
import { AddLinkModalComponent } from '../../shared/ui/add-link-modal/add-link-modal.component';
import { CardDetailComponent } from './components/card-detail/card-detail.component';
import { CategoryAssignerModalComponent } from '../../shared/ui/category-assigner-modal/category-assigner-modal.component';
import { MoveCardModalComponent } from '../../shared/ui/move-card-modal/move-card-modal.component';
import { ResourceCardComponent } from './components/resource-card/resource-card.component';
import { PubBannerComponent } from './components/pub-banner/pub-banner.component';

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
  type: 'OFFICIAL' | 'PARTNER' | 'PRIVATE';
  items?: ResourceItem[];
  partner: { id: number; nom: string; logo: string | null } | null;
  is_favorite: boolean;
  note_courte: string;
  note_longue: string;
  pharmacy_count?: number;
  is_featured?: boolean;
  ordre?: number;
  icon?: string | null;
}

export interface Category {
  id: number;
  nom: string;
  cards: ResourceCard[];
  adopted_cards?: ResourceCard[];
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    HeaderComponent,
    CardDetailComponent,
    CategoryAssignerModalComponent,
    AddLinkModalComponent,
    MoveCardModalComponent,
    ResourceCardComponent,
    PubBannerComponent,
  ],
  templateUrl: './dashboard.component.html',
  styleUrl: './dashboard.component.css'
})
export class DashboardComponent implements OnInit {
  private api = inject(DashboardApiService);
  private display = inject(DashboardDisplayService);
  private pharmacyService = inject(PharmacyService);
  private toast = inject(ToastService);
  private confirmService = inject(ConfirmService);
  private authService = inject(AuthService);
  private router = inject(Router);

  // Données
  allCategories: Category[] = [];
  displayedCategories: Category[] = [];
  libraryItems: any[] = [];
  pharmacyName = '';
  isLoading = true;

  // Filtres
  activeFilter = 'Tous';
  isExpanded = false;
  readonly VISIBLE_COUNT = 3;
  showOnlyFavorites = false;
  searchTerm = '';
  isSearching = false;

  // Modes & modales
  isEditMode = false;
  showAddModal = false;
  showAddCategoryModal = false;
  newCategoryName = '';

  // Carte ouverte
  openedCard: ResourceCard | null = null;
  selectedCardToAssign: ResourceCard | null = null;

  // Déplacement de carte
  cardToMove: ResourceCard | null = null;
  currentCategoryIdForMove: number | null = null;

  // Renommage catégorie
  editingCategoryId: number | null = null;
  editingCategoryName = '';

  // Drag & drop (conservé pour compatibilité future)
  draggedCard: ResourceCard | null = null;
  dragOverCard: ResourceCard | null = null;
  dragOverPosition: 'before' | 'after' | null = null;

  ngOnInit() {
    this.loadCategories();
    this.api.loadLibrary().subscribe({ next: data => this.libraryItems = data });
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: data => this.pharmacyName = data.nom_officine
    });
  }

  // ============================================================
  // CHARGEMENT
  // ============================================================

  loadCategories() {
    this.api.loadCategories().subscribe({
      next: (data) => {
        const raw = Array.isArray(data) ? data : data.results || [];
        this.allCategories = raw.map((cat: Category) => ({
          ...cat,
          cards: (cat.cards || []).map((c: ResourceCard) => ({ ...c, items: c.items || [] })),
          adopted_cards: (cat.adopted_cards || []).map((c: ResourceCard) => ({ ...c, items: c.items || [] }))
        }));
        this.updateDisplay();
        this.isLoading = false;
      },
      error: err => { console.error('Erreur chargement catégories', err); this.isLoading = false; }
    });
  }

  private updateDisplay() {
    if (this.isSearching && this.searchTerm) {
      this.displayedCategories = this.display.search(this.allCategories, this.searchTerm);
    } else {
      this.displayedCategories = this.display.buildDisplay(this.allCategories, this.showOnlyFavorites);
    }
  }

  // ============================================================
  // FILTRE PILLS & RECHERCHE
  // ============================================================

  setFilter(filter: string) {
    this.isExpanded = false;
    this.activeFilter = filter;
    this.showOnlyFavorites = (filter === 'Favoris');
    this.updateDisplay();
  }

  onSearch(term: string) {
    this.searchTerm = term.toLowerCase().trim();
    this.isSearching = !!this.searchTerm;
    this.updateDisplay();
  }

  getFilteredCards(): ResourceCard[] {
    const seen = new Set<number>();
    const allCards: ResourceCard[] = [];
    for (const cat of this.allCategories) {
      for (const c of (cat.cards || [])) {
        if (!seen.has(c.id)) { seen.add(c.id); allCards.push(c); }
      }
      for (const c of (cat.adopted_cards || [])) {
        if (!seen.has(c.id)) { seen.add(c.id); allCards.push(c); }
      }
    }

    let filtered = allCards;

    // Recherche textuelle
    if (this.searchTerm) {
      filtered = filtered.filter(c =>
        c.titre.toLowerCase().includes(this.searchTerm) ||
        (c.description_officielle || '').toLowerCase().includes(this.searchTerm) ||
        (c.partner?.nom || '').toLowerCase().includes(this.searchTerm) ||
        (c.note_courte || '').toLowerCase().includes(this.searchTerm)
      );
    }

    // Filtre par pill
    if (this.activeFilter === 'Favoris') {
      filtered = filtered.filter(c => c.is_favorite);
    } else if (this.activeFilter !== 'Tous') {
      const cat = this.allCategories.find(c => c.nom === this.activeFilter);
      if (cat) {
        const ids = new Set([
          ...(cat.cards || []).map(c => c.id),
          ...(cat.adopted_cards || []).map(c => c.id)
        ]);
        filtered = filtered.filter(c => ids.has(c.id));
      }
    }

    return filtered;
  }

  // ============================================================
  // HELPERS CARTES
  // ============================================================

  getCardCategory(card: ResourceCard): string {
    for (const cat of this.allCategories) {
      if (cat.cards?.some(c => c.id === card.id) || cat.adopted_cards?.some(c => c.id === card.id)) {
        return cat.nom;
      }
    }
    return '';
  }

  getCardCategoryId(card: ResourceCard): number {
    for (const cat of this.allCategories) {
      if (cat.cards?.some(c => c.id === card.id) || cat.adopted_cards?.some(c => c.id === card.id)) {
        return cat.id;
      }
    }
    return 0;
  }

  // ============================================================
  // AUTH
  // ============================================================

  handleLogout() {
    this.authService.logout();
  }

  // ============================================================
  // CATÉGORIES
  // ============================================================

  createCategoryFromDashboard() {
    if (!this.newCategoryName.trim()) return;
    const name = this.newCategoryName.trim();
    this.showAddCategoryModal = false;
    this.newCategoryName = '';
    this.api.createCategory(name).subscribe({
      next: (cat: any) => {
        this.allCategories.push({ id: cat.id, nom: cat.nom, cards: [], adopted_cards: [] });
        this.updateDisplay();
      },
      error: err => { console.error(err); this.toast.error('Erreur lors de la création de la catégorie.'); }
    });
  }

  async deleteCategory(category: Category) {
    const count = category.cards?.length || 0;
    const msg = count > 0
      ? `Supprimer "${category.nom}" et ses ${count} carte(s) ?`
      : `Supprimer la catégorie "${category.nom}" ?`;
    if (!await this.confirmService.ask({ title: 'Supprimer la catégorie', message: msg, danger: true })) return;

    const idx = this.allCategories.findIndex(c => c.id === category.id);
    if (idx >= 0) this.allCategories.splice(idx, 1);
    if (this.activeFilter === category.nom) this.activeFilter = 'Tous';
    this.updateDisplay();

    this.api.deleteCategory(category.id).subscribe({
      error: err => { console.error(err); this.toast.error('Erreur lors de la suppression.'); this.loadCategories(); }
    });
  }

  startRename(category: Category) { this.editingCategoryId = category.id; this.editingCategoryName = category.nom; }
  cancelRename() { this.editingCategoryId = null; this.editingCategoryName = ''; }

  saveRename(category: Category) {
    if (!this.editingCategoryName.trim()) { this.toast.warning('Le nom ne peut pas être vide.'); return; }
    const newName = this.editingCategoryName.trim();
    const oldName = category.nom;
    if (this.activeFilter === oldName) this.activeFilter = newName;
    category.nom = newName;
    this.cancelRename();
    this.updateDisplay();
    this.api.renameCategory(category.id, newName).subscribe({
      error: err => {
        console.error(err);
        category.nom = oldName;
        this.updateDisplay();
        this.toast.error(err.error?.nom?.[0] || 'Erreur lors du renommage.');
      }
    });
  }

  isFirstCategory(cat: Category) { return this.displayedCategories.indexOf(cat) === 0; }
  isLastCategory(cat: Category) { return this.displayedCategories.indexOf(cat) === this.displayedCategories.length - 1; }

  moveCategoryUp(category: Category) {
    const i = this.displayedCategories.indexOf(category);
    if (i <= 0) return;
    [this.displayedCategories[i - 1], this.displayedCategories[i]] = [this.displayedCategories[i], this.displayedCategories[i - 1]];
    const j = this.allCategories.findIndex(c => c.id === category.id);
    if (j > 0) [this.allCategories[j - 1], this.allCategories[j]] = [this.allCategories[j], this.allCategories[j - 1]];
    this.saveOrder();
  }

  moveCategoryDown(category: Category) {
    const i = this.displayedCategories.indexOf(category);
    if (i >= this.displayedCategories.length - 1) return;
    [this.displayedCategories[i], this.displayedCategories[i + 1]] = [this.displayedCategories[i + 1], this.displayedCategories[i]];
    const j = this.allCategories.findIndex(c => c.id === category.id);
    if (j < this.allCategories.length - 1) [this.allCategories[j], this.allCategories[j + 1]] = [this.allCategories[j + 1], this.allCategories[j]];
    this.saveOrder();
  }

  private saveOrder() {
    this.api.reorderCategories(this.displayedCategories.map(c => c.id)).subscribe({
      error: err => { console.error(err); this.loadCategories(); }
    });
  }

  // ============================================================
  // ACTIONS CARTES
  // ============================================================

  toggleEditMode() {
    this.isEditMode = !this.isEditMode;
    if (!this.isEditMode) this.cancelRename();
  }

  openCard(card: ResourceCard) {
    if (this.isEditMode) return;
    this.openedCard = card;
  }

  closeDetail() { this.openedCard = null; }
  closeDetailAndRefresh() { this.openedCard = null; }

  onCardUpdated(updatedCard: any) {
    if (this.openedCard && this.openedCard.id === updatedCard.id) Object.assign(this.openedCard, updatedCard);
    if (this.display.updateCardInCategories(this.allCategories, updatedCard)) this.updateDisplay();
  }

  toggleFavorite(card: ResourceCard, event: MouseEvent) {
    event.stopPropagation();
    card.is_favorite = !card.is_favorite;
    this.api.toggleCardFavorite(card.id).subscribe({
      next: (res) => {
        card.is_favorite = res.is_favorite;
        this.display.updateCardInCategories(this.allCategories, { id: card.id, is_favorite: res.is_favorite });
        this.updateDisplay();
      },
      error: () => { card.is_favorite = !card.is_favorite; }
    });
  }

  async hideOrDeleteCard(card: ResourceCard, event: MouseEvent) {
    event.stopPropagation();
    if (card.type === 'PRIVATE') {
      if (!await this.confirmService.ask({ title: 'Supprimer la carte', message: `Supprimer définitivement la carte "${card.titre}" ?`, danger: true })) return;
    } else {
      if (!await this.confirmService.ask({ title: 'Masquer la carte', message: `Masquer la carte "${card.titre}" de votre tableau de bord ?`, danger: true })) return;
    }

    this._removeCardFromAll(card.id);
    this.updateDisplay();

    const req = card.type === 'PRIVATE'
      ? this.api.deleteCard(card.id)
      : this.api.toggleCardVisibility(card.id);

    req.subscribe({
      error: err => { console.error(err); this.toast.error('Erreur — la carte a été restaurée.'); this.loadCategories(); }
    });
  }

  private _removeCardFromAll(cardId: number) {
    for (const cat of this.allCategories) {
      cat.cards = cat.cards.filter(c => c.id !== cardId);
      if (cat.adopted_cards) cat.adopted_cards = cat.adopted_cards.filter(c => c.id !== cardId);
    }
  }

  openMoveCardModal(card: ResourceCard, categoryId: number, event: MouseEvent) {
    event.stopPropagation();
    this.cardToMove = card;
    this.currentCategoryIdForMove = categoryId;
  }

  moveCard(newCategoryId: number) {
    if (!this.cardToMove) return;
    const card = this.cardToMove;
    this.cardToMove = null;
    this.currentCategoryIdForMove = null;
    this._removeCardFromAll(card.id);
    const destCat = this.allCategories.find(c => c.id === newCategoryId);
    if (destCat) destCat.cards.push(card);
    this.updateDisplay();

    const req = card.type === 'PRIVATE'
      ? this.api.movePrivateCard(card.id, newCategoryId)
      : this.api.assignCardCategory(card.id, newCategoryId);

    req.subscribe({
      error: err => { console.error(err); this.toast.error('Erreur lors du déplacement.'); this.loadCategories(); }
    });
  }

  handleCardSelection(card: ResourceCard) { this.showAddModal = false; this.selectedCardToAssign = card; }

  assignCategory(categoryId: number) {
    if (!this.selectedCardToAssign) return;
    this.api.assignCardCategory(this.selectedCardToAssign.id, categoryId).subscribe({
      next: () => { this.selectedCardToAssign = null; this.loadCategories(); this.toast.success('Ressource ajoutée !'); },
      error: err => { console.error(err); this.toast.error('Erreur d\'assignation.'); this.selectedCardToAssign = null; }
    });
  }

  onLinkAdded(data: any) {
    if (!this.allCategories.length) { this.toast.warning('Créez d\'abord une catégorie.'); return; }
    const formData = new FormData();
    formData.append('titre', data.title);
    formData.append('category', data.category || this.allCategories[0].id);
    if (data.type === 'WEB') { formData.append('type', 'WEB'); formData.append('url', data.url); }
    else { formData.append('type', 'PDF'); formData.append('document', data.file); }
    this.api.createCard(formData).subscribe({
      next: () => { this.showAddModal = false; this.loadCategories(); },
      error: err => { console.error(err); this.toast.error('Erreur lors de l\'ajout.'); }
    });
  }

  // ============================================================
  // BADGES (conservés pour usage dans les modales existantes)
  // ============================================================

  getBadgeClass(cardType: string): string {
    switch (cardType) {
      case 'PRIVATE': return 'badge-private';
      case 'OFFICIAL': return 'badge-official';
      case 'PARTNER': return 'badge-partner';
      default: return '';
    }
  }

  trackCard(_: number, card: ResourceCard): number { return card.id; }

  getBadgeLabel(cardType: string): string {
    switch (cardType) {
      case 'PRIVATE': return 'Privée';
      case 'OFFICIAL': return 'Validé';
      case 'PARTNER': return 'Partenaire';
      default: return '';
    }
  }
}
