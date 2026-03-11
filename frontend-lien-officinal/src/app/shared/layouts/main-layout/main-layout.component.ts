import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { Subscription, interval, Subject } from 'rxjs';
import { startWith, switchMap, takeUntil } from 'rxjs/operators';

import { AuthService } from '../../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../../core/services/collaborator.service';
import { MessagingService } from '../../../core/services/messaging.service';
import { PharmacyService } from '../../../core/services/pharmacy.service';
import { TaskService } from '../../../core/services/task.service';

import { SidebarComponent } from '../../../features/dashboard/components/sidebar/sidebar.component';
import { PinModalComponent } from '../../../features/messaging/components/pin-modal/pin-modal.component';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent, PinModalComponent],
  templateUrl: './main-layout.component.html'
})
export class MainLayoutComponent implements OnInit, OnDestroy {
  private authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);
  private messagingService = inject(MessagingService);
  private pharmacyService = inject(PharmacyService);
  private taskService = inject(TaskService);

  team: Collaborator[] = [];
  pharmacyName = '';
  unreadMessagesCount = 0;
  unseenTasksCount = 0;

  activeSessionCollaborator: Collaborator | null = null;
  pendingCollaborator: Collaborator | null = null;
  showPinModal = false;

  private unreadSub: Subscription | null = null;
  private destroy$ = new Subject<void>();

  ngOnInit() {
    this.loadTeam();
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: (data) => { this.pharmacyName = data.nom_officine; }
    });
    this.unreadSub = this.messagingService.unreadCount$.subscribe(
      count => { this.unreadMessagesCount = count; }
    );
    this.startTaskUnseenPolling();
  }

  ngOnDestroy() {
    this.unreadSub?.unsubscribe();
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (data: any) => {
        this.team = Array.isArray(data) ? data : data.results || [];
        // Abonnement réactif : se met à jour quel que soit l'endroit qui change le collaborateur
        this.authService.collaborator$.pipe(takeUntil(this.destroy$)).subscribe(id => {
          this.activeSessionCollaborator = id ? (this.team.find(c => c.id === id) ?? null) : null;
        });
      }
    });
  }

  private startTaskUnseenPolling() {
    const collabId = this.authService.getCurrentCollaboratorId();
    if (!collabId) return;
    interval(30000).pipe(
      startWith(0),
      takeUntil(this.destroy$),
      switchMap(() => this.taskService.getUnseenCount(collabId))
    ).subscribe(r => { this.unseenTasksCount = r.unseen_count; });
  }

  openSession(collab: Collaborator) {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
  }

  onPinValidated() {
    // Le token collaborateur est déjà stocké par authService.collaboratorLogin()
    // et le stream collaborator$ a été mis à jour — il suffit de fermer la modale
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  onPinCancelled() {
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  closeCollaboratorSession() {
    this.activeSessionCollaborator = null;
    this.authService.clearCurrentCollaborator();
  }
}
