import { Component, EventEmitter, Input, Output, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Conversation } from '../../../../core/services/messaging.service';

@Component({
  selector: 'app-conversation-list',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './conversation-list.component.html',
})
export class ConversationListComponent implements OnChanges {
  @Input() conversations: Conversation[] = [];
  @Input() selectedId: string | null = null;
  @Input() loading = false;

  @Output() selected = new EventEmitter<Conversation>();
  @Output() newConversation = new EventEmitter<void>();

  searchTerm = '';
  filtered: Conversation[] = [];

  ngOnChanges(): void {
    this.applyFilter();
  }

  applyFilter(): void {
    const term = this.searchTerm.toLowerCase().trim();
    this.filtered = term
      ? this.conversations.filter(c => c.subject.toLowerCase().includes(term))
      : [...this.conversations];
  }

  onSearch(): void {
    this.applyFilter();
  }

  select(conv: Conversation): void {
    this.selected.emit(conv);
  }

  formatDate(dateStr: string): string {
    const date = new Date(dateStr);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
      return date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
  }

  getInitials(fullName: string): string {
    return fullName.split(' ').map(p => p[0]).join('').toUpperCase().slice(0, 2);
  }
}
