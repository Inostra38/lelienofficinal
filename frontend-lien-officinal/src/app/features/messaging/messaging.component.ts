import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { interval, Subscription, switchMap } from 'rxjs';

import { MessagingService, Conversation } from '../../core/services/messaging.service';
import { AuthService } from '../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { InactivityService } from '../../core/services/inactivity.service';
import { ConversationListComponent } from './components/conversation-list/conversation-list.component';
import { ConversationDetailComponent } from './components/conversation-detail/conversation-detail.component';
import { NewConversationDialogComponent } from './components/new-conversation-dialog/new-conversation-dialog.component';
import { PinModalComponent } from './components/pin-modal/pin-modal.component';

@Component({
  selector: 'app-messaging',
  standalone: true,
  imports: [CommonModule, ConversationListComponent, ConversationDetailComponent, NewConversationDialogComponent, PinModalComponent],
  templateUrl: './messaging.component.html',
})
export class MessagingComponent implements OnInit, OnDestroy {
  private messagingService = inject(MessagingService);
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);
  private inactivityService = inject(InactivityService);
  private router = inject(Router);

  // ── État ────────────────────────────────────────────────────────────────
  conversations: Conversation[] = [];
  selectedConversation: Conversation | null = null;
  team: Collaborator[] = [];
  activeCollaborator: Collaborator | null = null;

  loadingConversations = false;
  showCollaboratorPicker = false;
  showNewConversationDialog = false;
  totalUnread = 0;

  // ── PIN switch ───────────────────────────────────────────────────────────
  /** Collaborateur en attente de validation PIN (switch) */
  pendingCollaborator: Collaborator | null = null;
  showPinModal = false;

  // ── Verrouillage auto ────────────────────────────────────────────────────
  isLocked = false;

  private subs = new Subscription();
  private listPollingSub: Subscription | null = null;

  // ── Cycle de vie ─────────────────────────────────────────────────────────

  ngOnInit(): void {
    this.loadTeam();

    // Verrouillage auto après 5 min d'inactivité
    this.inactivityService.startWatching();
    this.subs.add(
      this.inactivityService.onLocked().subscribe(() => {
        if (this.activeCollaborator) {
          this.isLocked = true;
          this.stopListPolling();
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
    this.stopListPolling();
    this.inactivityService.stopWatching();
  }

  // ── Équipe & collaborateur actif ─────────────────────────────────────────

  loadTeam(): void {
    this.collaboratorService.getTeam().subscribe({
      next: (team) => {
        this.team = team;
        // Abonnement réactif : reagit à tout changement de collaborateur (sidebar, tâches, ici)
        this.subs.add(
          this.authService.collaborator$.subscribe(id => {
            const found = id ? team.find(c => c.id === id) ?? null : null;
            if (!found) {
              this.stopListPolling();
              this.activeCollaborator = null;
              this.showCollaboratorPicker = true;
              return;
            }
            if (found.id === this.activeCollaborator?.id) {
              // Même collaborateur — si verrouillé, le déverrouiller (PIN déjà validé ailleurs)
              if (this.isLocked) {
                this.isLocked = false;
                this.startListPolling();
                this.inactivityService.resetTimer();
              }
              return;
            }
            // Nouveau collaborateur (depuis sidebar ou ici après PIN)
            this.isLocked = false;
            this.showPinModal = false;
            this.pendingCollaborator = null;
            this.setActiveCollaborator(found);
          })
        );
      },
      error: () => {
        this.showCollaboratorPicker = true;
      }
    });
  }

  /** Intercepte le clic sur un collaborateur — ouvre la modal PIN */
  selectCollaborator(collab: Collaborator): void {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
    this.showCollaboratorPicker = false;
  }

  /** Appelé quand le PIN est validé (switch ou unlock) */
  onPinValidated(): void {
    this.showPinModal = false;

    if (this.isLocked) {
      // Mode unlock : même collaborateur, déverrouiller localement
      this.isLocked = false;
      this.startListPolling();
      this.inactivityService.resetTimer();
      this.pendingCollaborator = null;
    } else if (this.pendingCollaborator) {
      // Mode switch : émet vers le stream → met à jour sidebar + tâches automatiquement
      this.messagingService.setActiveCollaboratorId(this.pendingCollaborator.id!);
      this.pendingCollaborator = null;
      // setActiveCollaborator sera appelé par le stream
    }
  }

  onPinCancelled(): void {
    this.showPinModal = false;
    this.pendingCollaborator = null;
    // Si aucun collaborateur actif, rouvrir le sélecteur
    if (!this.activeCollaborator) {
      this.showCollaboratorPicker = true;
    }
  }

  private setActiveCollaborator(collab: Collaborator): void {
    this.activeCollaborator = collab;
    this.showCollaboratorPicker = false;
    this.loadConversations();
    this.startListPolling();
  }

  changeCollaborator(): void {
    this.stopListPolling();
    this.isLocked = false;
    this.activeCollaborator = null;
    this.selectedConversation = null;
    this.conversations = [];
    this.totalUnread = 0;
    this.messagingService.clearActiveCollaborator();
    this.showCollaboratorPicker = true;
  }

  // ── Conversations ────────────────────────────────────────────────────────

  loadConversations(): void {
    this.loadingConversations = true;
    this.subs.add(
      this.messagingService.getConversations().subscribe({
        next: (data) => {
          this.conversations = data;
          this.totalUnread = data.reduce((sum, c) => sum + c.unread_count, 0);
          this.messagingService.setUnreadCount(this.totalUnread);
          this.loadingConversations = false;
        },
        error: () => { this.loadingConversations = false; }
      })
    );
  }

  private startListPolling(): void {
    this.stopListPolling();
    this.listPollingSub = interval(10000).pipe(
      switchMap(() => this.messagingService.getConversations())
    ).subscribe({
      next: (data) => {
        this.conversations = data;
        this.totalUnread = data.reduce((sum, c) => sum + c.unread_count, 0);
        this.messagingService.setUnreadCount(this.totalUnread);
      }
    });
  }

  private stopListPolling(): void {
    this.listPollingSub?.unsubscribe();
    this.listPollingSub = null;
  }

  onConversationSelected(conv: Conversation): void {
    this.selectedConversation = conv;
    this.messagingService.markAsRead(conv.id).subscribe();
  }

  onNewConversation(): void {
    this.showNewConversationDialog = true;
  }

  onConversationCreated(conv: Conversation): void {
    this.showNewConversationDialog = false;
    this.loadConversations();
    this.selectedConversation = conv;
  }

  onConversationDeleted(): void {
    this.selectedConversation = null;
    this.loadConversations();
  }

  // ── Navigation ───────────────────────────────────────────────────────────

  goToDashboard(): void {
    this.router.navigate(['/dashboard']);
  }

  logout(): void {
    this.authService.logout();
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  getInitials(collab: Collaborator): string {
    return `${collab.first_name[0]}${collab.last_name[0]}`.toUpperCase();
  }

  getCollaboratorBgClass(color: string): string {
    return `bg-${color}-500`;
  }
}
