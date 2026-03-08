import { Component, EventEmitter, Input, Output, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { MessagingService, Conversation } from '../../../../core/services/messaging.service';
import { Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-new-conversation-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './new-conversation-dialog.component.html',
})
export class NewConversationDialogComponent implements OnInit {
  /** Collaborateurs disponibles (fournis par le parent) */
  @Input() teamMembers: Collaborator[] = [];
  /** ID du collaborateur actif (exclu de la sélection — il est auto-participant) */
  @Input() activeCollaboratorId: number | null = null;

  @Output() created = new EventEmitter<Conversation>();
  @Output() cancelled = new EventEmitter<void>();

  private messagingService = inject(MessagingService);

  // ── État du formulaire ───────────────────────────────────────────────────
  subject = '';
  selectedIds: Set<number> = new Set();
  submitting = false;
  error = '';

  /** Membres sélectionnables (tous sauf le collaborateur actif) */
  get selectableMembers(): Collaborator[] {
    return this.teamMembers.filter(m => m.id !== this.activeCollaboratorId);
  }

  ngOnInit(): void {
    // Pré-sélectionne tous les membres par défaut
    this.selectableMembers.forEach(m => this.selectedIds.add(m.id!));
  }

  // ── Sélection des participants ───────────────────────────────────────────

  toggleMember(id: number): void {
    if (this.selectedIds.has(id)) {
      this.selectedIds.delete(id);
    } else {
      this.selectedIds.add(id);
    }
  }

  isSelected(id: number): boolean {
    return this.selectedIds.has(id);
  }

  selectAll(): void {
    this.selectableMembers.forEach(m => this.selectedIds.add(m.id!));
  }

  deselectAll(): void {
    this.selectedIds.clear();
  }

  get allSelected(): boolean {
    return this.selectableMembers.every(m => this.selectedIds.has(m.id!));
  }

  // ── Soumission ───────────────────────────────────────────────────────────

  get isValid(): boolean {
    return this.subject.trim().length > 0 && this.selectedIds.size > 0;
  }

  submit(): void {
    if (!this.isValid || this.submitting) return;

    this.submitting = true;
    this.error = '';

    const participantIds = Array.from(this.selectedIds);

    this.messagingService.createConversation(this.subject.trim(), participantIds).subscribe({
      next: (conv) => {
        this.submitting = false;
        this.created.emit(conv);
      },
      error: (err) => {
        this.submitting = false;
        this.error = err?.error?.subject?.[0]
          || err?.error?.participant_ids?.[0]
          || err?.error?.detail
          || 'Une erreur est survenue.';
      }
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  getInitials(collab: Collaborator): string {
    return `${collab.first_name[0]}${collab.last_name[0]}`.toUpperCase();
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }
}
