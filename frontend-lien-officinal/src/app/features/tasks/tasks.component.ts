import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Subject, Subscription } from 'rxjs';
import { takeUntil } from 'rxjs/operators';
import { CdkDragDrop, DragDropModule, moveItemInArray } from '@angular/cdk/drag-drop';

import { TaskService, Task } from '../../core/services/task.service';
import { TaskWebSocketService } from '../../core/services/task-websocket.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { AuthService } from '../../core/auth/auth.service';
import { PinModalComponent } from '../messaging/components/pin-modal/pin-modal.component';
import { TaskCardComponent } from './components/task-card/task-card.component';
import { TaskCreateDialogComponent } from './components/task-create-dialog/task-create-dialog.component';
import { TaskDetailDrawerComponent } from './components/task-detail-drawer/task-detail-drawer.component';

@Component({
  selector: 'app-tasks',
  standalone: true,
  imports: [CommonModule, DragDropModule, PinModalComponent, TaskCardComponent, TaskCreateDialogComponent, TaskDetailDrawerComponent],
  templateUrl: './tasks.component.html',
  styleUrl: './tasks.component.css'
})
export class TasksComponent implements OnInit, OnDestroy {
  private taskService = inject(TaskService);
  private taskWs = inject(TaskWebSocketService);
  private collaboratorService = inject(CollaboratorService);
  private authService = inject(AuthService);
  private router = inject(Router);
  private destroy$ = new Subject<void>();
  private subs = new Subscription();

  // Session collaborateur
  activeCollaborator: Collaborator | null = null;
  team: Collaborator[] = [];
  showCollaboratorPicker = false;
  pendingCollaborator: Collaborator | null = null;
  showPinModal = false;

  // Données
  personalTasks: Task[] = [];
  assignedToMe: Task[] = [];
  assignedByMe: Task[] = [];
  loading = false;
  unseenCount = 0;

  // UI
  showCreateDialog = false;
  createMode: 'personal' | 'assigned' = 'personal';
  showCreateDropdown = false;
  selectedTask: Task | null = null;
  collapsed: Record<string, boolean> = { personal: false, assigned_to_me: false, assigned_by_me: false };
  openedTaskIds = new Set<string>();

  ngOnInit() {
    this.collaboratorService.getTeam().subscribe(team => {
      this.team = team;
      // Abonnement réactif : reagit à tout changement (sidebar, messagerie, ici)
      this.subs.add(
        this.authService.collaborator$.subscribe(id => {
          const found = id ? team.find(c => c.id === id) ?? null : null;
          if (found?.id === this.activeCollaborator?.id) return; // pas de changement
          this.destroy$.next(); // arrêter les subscriptions en cours
          this.taskWs.disconnect();
          this.showPinModal = false;
          this.pendingCollaborator = null;
          if (found) {
            this.activeCollaborator = found;
            this.showCollaboratorPicker = false;
            this.startPolling();
          } else {
            this.activeCollaborator = null;
            this.showCollaboratorPicker = true;
          }
        })
      );
    });
  }

  selectCollaborator(collab: Collaborator) {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
  }

  onPinValidated() {
    if (!this.pendingCollaborator) return;
    this.authService.setCurrentCollaboratorId(this.pendingCollaborator.id!); // le stream gère la suite
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  onPinCancelled() {
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  changeCollaborator() {
    this.authService.clearCurrentCollaborator();
    this.activeCollaborator = null;
    this.destroy$.next();
    this.showCollaboratorPicker = true;
  }

  startPolling() {
    // Fetch initial
    this.refreshTasks();

    // Connexion WebSocket : refresh à chaque événement reçu
    this.taskWs.connect();
    this.taskWs.events$.pipe(takeUntil(this.destroy$)).subscribe(() => {
      this.refreshTasks();
    });
  }

  refreshUnseenCount() {
    if (!this.activeCollaborator) return;
    this.taskService.getUnseenCount(this.activeCollaborator.id!).subscribe(r => {
      this.unseenCount = r.unseen_count;
    });
  }

  toggleSection(section: string): void {
    this.collapsed[section] = !this.collapsed[section];
    if (section === 'assigned_by_me' && !this.collapsed[section] && this.unseenCount > 0) {
      this.taskService.markAsSeen(this.activeCollaborator!.id!).subscribe(() => {
        this.unseenCount = 0;
        this.assignedByMe = this.assignedByMe.map(t => ({ ...t, is_completion_seen: true }));
      });
    }
  }

  onFabClick(evt: Event) {
    evt.stopPropagation();
    if (this.activeCollaborator?.can_assign_task) {
      this.showCreateDropdown = !this.showCreateDropdown;
    } else {
      this.openCreate('personal');
    }
  }

  openCreate(mode: 'personal' | 'assigned') {
    this.createMode = mode;
    this.showCreateDialog = true;
    this.showCreateDropdown = false;
  }

  onTaskCreated() {
    this.showCreateDialog = false;
    this.refreshTasks();
  }

  onTaskAction(action: 'start' | 'complete' | 'delete' | 'reopen', task: Task) {
    switch (action) {
      case 'start':
        this.taskService.startTask(task.id).subscribe(() => this.refreshTasks());
        break;
      case 'complete':
        this.taskService.completeTask(task.id, this.activeCollaborator!.id!).subscribe(() => this.refreshTasks());
        break;
      case 'reopen':
        this.taskService.reopenTask(task.id).subscribe(() => this.refreshTasks());
        break;
      case 'delete':
        if (this.activeCollaborator?.id) {
          this.taskService.deleteTask(task.id, this.activeCollaborator.id).subscribe(() => this.refreshTasks());
        }
        break;
    }
  }

  openDetail(task: Task) {
    this.selectedTask = task;
    this.openedTaskIds.add(task.id);
  }

  onDrawerClosed() {
    this.selectedTask = null;
    this.refreshTasks();
  }

  refreshTasks() {
    if (!this.activeCollaborator?.id) return;
    this.taskService.getTasks(this.activeCollaborator.id).subscribe(data => {
      this.personalTasks = data.personal_tasks;
      this.assignedToMe = data.assigned_to_me;
      this.assignedByMe = data.assigned_by_me;
      this.refreshUnseenCount();
    });
  }

  getInitials(collab: Collaborator): string {
    return `${collab.first_name.charAt(0)}${collab.last_name.charAt(0)}`.toUpperCase();
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  onDrop(event: CdkDragDrop<Task[]>, group: 'personal' | 'assigned_to_me' | 'assigned_by_me') {
    if (event.previousIndex === event.currentIndex) return;
    const arr = group === 'personal' ? this.personalTasks
              : group === 'assigned_to_me' ? this.assignedToMe
              : this.assignedByMe;
    moveItemInArray(arr, event.previousIndex, event.currentIndex);
    this.taskService.reorderTasks(arr.map(t => t.id)).subscribe();
  }

  goToDashboard() {
    this.router.navigate(['/dashboard']);
  }

  ngOnDestroy() {
    this.subs.unsubscribe();
    this.destroy$.next();
    this.destroy$.complete();
    this.taskWs.disconnect();
  }
}
