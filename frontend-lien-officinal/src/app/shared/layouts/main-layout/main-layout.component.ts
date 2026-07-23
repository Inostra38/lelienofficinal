import { Component, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { Subscription, interval, Subject } from 'rxjs';
import { startWith, switchMap, takeUntil } from 'rxjs/operators';

import { AuthService } from '../../../core/auth/auth.service';
import { CollaboratorService, Collaborator } from '../../../core/services/collaborator.service';
import { resolveColor } from '../../../core/utils/collaborator-colors';
import { InactivityService } from '../../../core/services/inactivity.service';
import { MessagingService } from '../../../core/services/messaging.service';
import { PharmacyService } from '../../../core/services/pharmacy.service';
import { TaskService } from '../../../core/services/task.service';
import { QualityNotificationsService } from '../../../features/quality/services/quality-notifications.service';

import { SidebarComponent } from '../../../features/dashboard/components/sidebar/sidebar.component';
import { PinModalComponent } from '../../../features/messaging/components/pin-modal/pin-modal.component';
import { ToastComponent } from '../../components/toast/toast.component';
import { EmailBannerComponent } from '../../components/email-banner/email-banner.component';
import { SubscriptionBannerComponent } from '../../components/subscription-banner/subscription-banner.component';

@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent, PinModalComponent, ToastComponent, EmailBannerComponent, SubscriptionBannerComponent],
  templateUrl: './main-layout.component.html'
})
export class MainLayoutComponent implements OnInit, OnDestroy {
  authService = inject(AuthService);
  private collaboratorService = inject(CollaboratorService);
  private inactivityService = inject(InactivityService);
  private messagingService = inject(MessagingService);
  private pharmacyService = inject(PharmacyService);
  private taskService = inject(TaskService);
  private qualityNotifService = inject(QualityNotificationsService);

  team: Collaborator[] = [];
  teamLoaded = false;
  pharmacyName = '';
  pharmacyLogo = '';
  unreadMessagesCount = 0;
  unseenTasksCount = 0;
  unreadQualityCount = 0;

  activeSessionCollaborator: Collaborator | null = null;
  pendingCollaborator: Collaborator | null = null;
  showPinModal = false;
  showInactivityToast = false;

  get isLocked(): boolean {
    return this.activeSessionCollaborator === null;
  }

  private unreadSub: Subscription | null = null;
  private destroy$ = new Subject<void>();

  ngOnInit() {
    this.loadTeam();
    this.pharmacyService.getCurrentPharmacy().subscribe({
      next: (data) => {
        this.pharmacyName = data.nom_officine;
        this.pharmacyLogo = data.logo ?? '';
      }
    });
    this.unreadSub = this.messagingService.unreadCount$.subscribe(
      count => { this.unreadMessagesCount = count; }
    );
    this.startTaskUnseenPolling();
    this.qualityNotifService.unreadCount$.pipe(takeUntil(this.destroy$)).subscribe(
      count => { this.unreadQualityCount = count; }
    );
    this.startQualityNotifPolling();

    this.inactivityService.startWatching();
    this.inactivityService.onLocked().pipe(takeUntil(this.destroy$)).subscribe(() => {
      if (this.activeSessionCollaborator) {
        this.authService.clearCurrentCollaborator();
        this.showInactivityToast = true;
        setTimeout(() => { this.showInactivityToast = false; }, 4000);
      }
    });
  }

  ngOnDestroy() {
    this.unreadSub?.unsubscribe();
    this.inactivityService.stopWatching();
    this.destroy$.next();
    this.destroy$.complete();
  }

  private loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (data: any) => {
        this.team = Array.isArray(data) ? data : data.results || [];
        this.teamLoaded = true;
        // Abonnement réactif : se met à jour quel que soit l'endroit qui change le collaborateur
        this.authService.collaborator$.pipe(takeUntil(this.destroy$)).subscribe(id => {
          this.activeSessionCollaborator = id ? (this.team.find(c => c.id === id) ?? null) : null;
        });
      }
    });
  }

  getCollaboratorInitials(c: Collaborator): string {
    return ((c.first_name?.[0] ?? '') + (c.last_name?.[0] ?? '')).toUpperCase();
  }

  getCollaboratorColor(c: Collaborator): string {
    return resolveColor(c.color ?? '').base;
  }

  private startQualityNotifPolling() {
    const collabId = this.authService.getCurrentCollaboratorId();
    if (!collabId) return;
    interval(60000).pipe(
      startWith(0),
      takeUntil(this.destroy$),
      switchMap(() => this.qualityNotifService.load())
    ).subscribe();
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
