import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ResourceCard } from '../../dashboard.component';

@Component({
  selector: 'app-resource-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './resource-card.component.html'
})
export class ResourceCardComponent {
  @Input() card!: ResourceCard;
  @Input() categoryName = '';
  @Input() isEditMode = false;

  @Output() cardClick = new EventEmitter<ResourceCard>();
  @Output() favoriteToggle = new EventEmitter<{ card: ResourceCard; event: MouseEvent }>();
  @Output() moveCardRequest = new EventEmitter<{ card: ResourceCard; event: MouseEvent }>();
  @Output() deleteCardRequest = new EventEmitter<{ card: ResourceCard; event: MouseEvent }>();

  onCardClick() {
    if (!this.isEditMode) this.cardClick.emit(this.card);
  }

  getInitials(): string {
    const words = this.card.titre.trim().split(/\s+/);
    if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
    return this.card.titre.substring(0, 2).toUpperCase();
  }

  getLogoColors(): { bg: string; text: string; border: string } {
    switch (this.card.type) {
      case 'OFFICIAL': return { bg: '#f0fdf4', text: '#15803d', border: '#bbf7d0' };
      case 'PARTNER': return { bg: '#ecfdf5', text: '#059669', border: '#a7f3d0' };
      default:         return { bg: '#eff6ff', text: '#2563eb', border: '#bfdbfe' };
    }
  }

  getBadgeLabel(): string {
    switch (this.card.type) {
      case 'OFFICIAL': return 'Validé';
      case 'PARTNER':  return 'Partenaire';
      default:         return 'Privé';
    }
  }

  getLinkCount(): number {
    return this.card.items?.length || 0;
  }
}
