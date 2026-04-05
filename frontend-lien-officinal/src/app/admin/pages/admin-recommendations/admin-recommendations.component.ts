import { Component, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { environment } from '../../../../environments/environment';
import {
  RecommendationService,
  RecommendationCard,
  RecommendationItem,
  OfficialCard
} from '../../services/recommendation.service';

interface ResourceItemDetail {
  id: number;
  type: string;
  label: string;
  url: string;
  file: string | null;
  ordre: number;
}

interface CardDetail {
  id: number;
  titre: string;
  description_officielle: string;
  type: string;
  is_featured: boolean;
  items: ResourceItemDetail[];
}

@Component({
  selector: 'app-admin-recommendations',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-recommendations.component.html',
})
export class AdminRecommendationsComponent implements OnInit {
  private recService = inject(RecommendationService);
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/api/admin/resources`;

  cards: RecommendationCard[] = [];
  items: RecommendationItem[] = [];
  officialCards: OfficialCard[] = [];
  counts = { pending_cards: 0, pending_items: 0 };

  loading = false;
  currentStatus = 'PENDING';
  selectedTargetCards: { [itemId: number]: number } = {};

  // Modal édition carte
  showModal = false;
  editCard: CardDetail | null = null;
  editingRecCard: RecommendationCard | null = null;
  form = { titre: '', description_officielle: '' };
  saving = false;
  newItem = { type: 'WEB', label: '', url: '' };

  statusFilters = [
    { label: 'En attente', value: 'PENDING' },
    { label: 'Approuvées', value: 'APPROVED' },
    { label: 'Rejetées', value: 'REJECTED' },
    { label: 'Toutes', value: 'ALL' },
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
    this.loadRecommendations('PENDING');
    this.loadOfficialCards();
  }

  // ── Liste ──────────────────────────────────────────────────────────

  loadRecommendations(status: string): void {
    this.currentStatus = status;
    this.loading = true;
    this.recService.getRecommendations(status).subscribe({
      next: (res) => {
        this.cards = res.cards;
        this.items = res.items;
        this.counts = res.counts;
        this.loading = false;
      },
      error: () => { this.loading = false; }
    });
  }

  loadOfficialCards(): void {
    this.recService.getOfficialCards().subscribe({
      next: (res) => { this.officialCards = res.cards; }
    });
  }

  // ── Modal détail carte ─────────────────────────────────────────────

  openCardDetail(card: RecommendationCard): void {
    this.editingRecCard = card;
    this.form = { titre: card.titre, description_officielle: card.description_officielle || '' };
    this.newItem = { type: 'WEB', label: '', url: '' };
    this.showModal = true;

    this.http.get<CardDetail>(`${this.baseUrl}/${card.id}/`).subscribe({
      next: (detail) => { this.editCard = detail; },
    });
  }

  closeModal(): void {
    this.showModal = false;
    this.editCard = null;
    this.editingRecCard = null;
  }

  saveChanges(): void {
    if (!this.editCard || !this.form.titre.trim()) return;
    this.saving = true;
    this.http.patch<any>(`${this.baseUrl}/${this.editCard.id}/`, this.form).subscribe({
      next: (res) => {
        this.saving = false;
        if (this.editCard) {
          this.editCard.titre = res.titre;
          this.editCard.description_officielle = res.description_officielle;
        }
        if (this.editingRecCard) {
          this.editingRecCard.titre = res.titre;
          this.editingRecCard.description_officielle = res.description_officielle;
        }
      },
      error: () => { this.saving = false; },
    });
  }

  approveFromModal(): void {
    if (!this.editingRecCard) return;

    // Sauvegarder d'abord les modifications si le titre a changé
    const needsSave = this.editCard &&
      (this.form.titre !== this.editCard.titre || this.form.description_officielle !== this.editCard.description_officielle);

    const doApprove = () => {
      this.recService.approveCard(this.editingRecCard!.id).subscribe({
        next: () => {
          this.cards = this.cards.filter(c => c.id !== this.editingRecCard!.id);
          this.counts.pending_cards--;
          this.closeModal();
        },
      });
    };

    if (needsSave) {
      this.http.patch<any>(`${this.baseUrl}/${this.editCard!.id}/`, this.form).subscribe({
        next: () => doApprove(),
      });
    } else {
      doApprove();
    }
  }

  rejectFromModal(): void {
    if (!this.editingRecCard) return;
    this.recService.reject('card', this.editingRecCard.id).subscribe({
      next: () => {
        this.cards = this.cards.filter(c => c.id !== this.editingRecCard!.id);
        this.counts.pending_cards--;
        this.closeModal();
      },
    });
  }

  // ── Items (dans le modal) ──────────────────────────────────────────

  addItem(): void {
    if (!this.editCard || !this.newItem.label.trim()) return;
    this.http.post<ResourceItemDetail>(`${this.baseUrl}/${this.editCard.id}/items/`, this.newItem).subscribe({
      next: (item) => {
        this.editCard!.items.push(item);
        this.newItem = { type: 'WEB', label: '', url: '' };
      },
    });
  }

  deleteItem(item: ResourceItemDetail): void {
    this.http.delete(`${this.baseUrl}/items/${item.id}/`).subscribe({
      next: () => {
        if (this.editCard) {
          this.editCard.items = this.editCard.items.filter(i => i.id !== item.id);
        }
      },
    });
  }

  // ── Actions directes (sans modal) ─────────────────────────────────

  approveCard(card: RecommendationCard): void {
    this.recService.approveCard(card.id).subscribe({
      next: () => {
        this.cards = this.cards.filter(c => c.id !== card.id);
        this.counts.pending_cards--;
      }
    });
  }

  approveItem(item: RecommendationItem): void {
    const targetId = this.selectedTargetCards[item.id];
    this.recService.approveItem(item.id, targetId).subscribe({
      next: () => {
        this.items = this.items.filter(i => i.id !== item.id);
        this.counts.pending_items--;
      }
    });
  }

  reject(type: 'card' | 'item', rec: RecommendationCard | RecommendationItem): void {
    this.recService.reject(type, rec.id).subscribe({
      next: () => {
        if (type === 'card') {
          this.cards = this.cards.filter(c => c.id !== rec.id);
          this.counts.pending_cards--;
        } else {
          this.items = this.items.filter(i => i.id !== rec.id);
          this.counts.pending_items--;
        }
      }
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

  getFileUrl(path: string): string {
    if (path.startsWith('http')) return path;
    return `${environment.apiUrl}${path}`;
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
