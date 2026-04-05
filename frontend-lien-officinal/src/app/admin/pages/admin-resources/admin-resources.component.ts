import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';

interface ResourceCard {
  id: number;
  titre: string;
  description_officielle: string;
  type: 'OFFICIAL' | 'PARTNER' | 'PRIVATE';
  is_featured: boolean;
  pharmacy_count: number;
}

interface ResourceItem {
  id: number;
  type: string;
  label: string;
  url: string;
  file: string | null;
  ordre: number;
}

interface CardDetail extends ResourceCard {
  items: ResourceItem[];
}

@Component({
  selector: 'app-admin-resources',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-resources.component.html',
})
export class AdminResourcesComponent implements OnInit {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/api/admin/resources`;

  cards: ResourceCard[] = [];
  filteredCards: ResourceCard[] = [];
  loading = false;
  activeType = 'ALL';
  searchTerm = '';

  // Modale
  showModal = false;
  isEditing = false;
  saving = false;
  editCard: CardDetail | null = null;

  // Formulaire
  form = { titre: '', description_officielle: '', type: 'OFFICIAL' as string, is_featured: false };

  // Ajout d'item
  newItem = { type: 'WEB', label: '', url: '' };

  typeFilters = [
    { label: 'Toutes', value: 'ALL' },
    { label: 'Officielles', value: 'OFFICIAL' },
    { label: 'Partenaires', value: 'PARTNER' },
    { label: 'Privées', value: 'PRIVATE' },
  ];

  typeOptions = [
    { label: 'Officielle', value: 'OFFICIAL' },
    { label: 'Partenaire', value: 'PARTNER' },
    { label: 'Privée', value: 'PRIVATE' },
  ];

  itemTypeOptions = [
    { label: 'Site Web', value: 'WEB' },
    { label: 'PDF', value: 'PDF' },
    { label: 'Téléphone', value: 'TEL' },
    { label: 'Email', value: 'MAIL' },
  ];

  private palettes = [
    { background: '#EAF3DE', color: '#27500A' },
    { background: '#E6F1FB', color: '#0C447C' },
    { background: '#EEEDFE', color: '#3C3489' },
    { background: '#E1F5EE', color: '#085041' },
    { background: '#FAECE7', color: '#712B13' },
    { background: '#FBEAF0', color: '#72243E' },
  ];

  ngOnInit(): void {
    this.loadCards();
  }

  // ── Liste ──────────────────────────────────────────────────────────

  loadCards(): void {
    this.loading = true;
    this.http.get<any>(`${this.baseUrl}/`).subscribe({
      next: (res) => {
        this.cards = Array.isArray(res) ? res : res.results || [];
        this.applyFilters();
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  setType(type: string): void {
    this.activeType = type;
    this.applyFilters();
  }

  onSearch(): void {
    this.applyFilters();
  }

  private applyFilters(): void {
    let result = this.cards;
    if (this.activeType !== 'ALL') {
      result = result.filter(c => c.type === this.activeType);
    }
    if (this.searchTerm.trim()) {
      const term = this.searchTerm.toLowerCase();
      result = result.filter(c =>
        c.titre.toLowerCase().includes(term) ||
        (c.description_officielle || '').toLowerCase().includes(term)
      );
    }
    this.filteredCards = result;
  }

  // ── Modale création ────────────────────────────────────────────────

  openCreate(): void {
    this.isEditing = false;
    this.editCard = null;
    this.form = { titre: '', description_officielle: '', type: 'OFFICIAL', is_featured: false };
    this.newItem = { type: 'WEB', label: '', url: '' };
    this.showModal = true;
  }

  // ── Modale édition ─────────────────────────────────────────────────

  openEdit(card: ResourceCard): void {
    this.isEditing = true;
    this.form = {
      titre: card.titre,
      description_officielle: card.description_officielle,
      type: card.type,
      is_featured: card.is_featured,
    };
    this.newItem = { type: 'WEB', label: '', url: '' };
    this.showModal = true;

    // Charger le détail avec items
    this.http.get<CardDetail>(`${this.baseUrl}/${card.id}/`).subscribe({
      next: (detail) => { this.editCard = detail; },
    });
  }

  closeModal(): void {
    this.showModal = false;
    this.editCard = null;
  }

  // ── Sauvegarde ─────────────────────────────────────────────────────

  save(): void {
    if (!this.form.titre.trim()) return;
    this.saving = true;

    if (this.isEditing && this.editCard) {
      this.http.patch<any>(`${this.baseUrl}/${this.editCard.id}/`, this.form).subscribe({
        next: () => { this.saving = false; this.closeModal(); this.loadCards(); },
        error: () => { this.saving = false; },
      });
    } else {
      this.http.post<any>(`${this.baseUrl}/`, this.form).subscribe({
        next: (created) => {
          this.saving = false;
          // Passer en mode édition pour pouvoir ajouter des items
          this.isEditing = true;
          this.editCard = { ...created, items: [] };
        },
        error: () => { this.saving = false; },
      });
    }
  }

  // ── Items ──────────────────────────────────────────────────────────

  addItem(): void {
    if (!this.editCard || !this.newItem.label.trim()) return;
    this.http.post<ResourceItem>(`${this.baseUrl}/${this.editCard.id}/items/`, this.newItem).subscribe({
      next: (item) => {
        this.editCard!.items.push(item);
        this.newItem = { type: 'WEB', label: '', url: '' };
      },
    });
  }

  deleteItem(item: ResourceItem): void {
    this.http.delete(`${this.baseUrl}/items/${item.id}/`).subscribe({
      next: () => {
        if (this.editCard) {
          this.editCard.items = this.editCard.items.filter(i => i.id !== item.id);
        }
      },
    });
  }

  // ── Suppression ressource ──────────────────────────────────────────

  deleteCard(): void {
    if (!this.editCard || !confirm(`Supprimer la ressource "${this.editCard.titre}" ?`)) return;
    this.http.delete(`${this.baseUrl}/${this.editCard.id}/`).subscribe({
      next: () => { this.closeModal(); this.loadCards(); },
    });
  }

  // ── Helpers UI ─────────────────────────────────────────────────────

  getInitials(titre: string): string {
    if (!titre) return '?';
    const words = titre.trim().split(/\s+/);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return titre.substring(0, 2).toUpperCase();
  }

  getAvatarStyle(titre: string): { background: string; color: string } {
    const hash = titre.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0);
    return this.palettes[hash % this.palettes.length];
  }

  getTypeBadge(type: string): { label: string; classes: string } {
    switch (type) {
      case 'OFFICIAL': return { label: 'Officielle', classes: 'bg-green-50 text-green-700' };
      case 'PARTNER': return { label: 'Partenaire', classes: 'bg-emerald-50 text-emerald-700' };
      case 'PRIVATE': return { label: 'Privée', classes: 'bg-blue-50 text-blue-600' };
      default: return { label: type, classes: 'bg-gray-50 text-gray-600' };
    }
  }

  getItemTypeIcon(type: string): string {
    switch (type) {
      case 'WEB': return '🌐';
      case 'PDF': return '📄';
      case 'TEL': return '📞';
      case 'MAIL': return '✉️';
      default: return '🔗';
    }
  }
}
