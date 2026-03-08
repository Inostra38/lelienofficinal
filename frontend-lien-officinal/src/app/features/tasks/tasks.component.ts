import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Router } from '@angular/router';
import { Subject, interval } from 'rxjs';
import { takeUntil, switchMap, startWith } from 'rxjs/operators';

import { TaskService, Task } from '../../core/services/task.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { AuthService } from '../../core/auth/auth.service';
import { PinModalComponent } from '../messaging/components/pin-modal/pin-modal.component';
import { TaskCardComponent } from './components/task-card/task-card.component';
import { TaskCreateDialogComponent } from './components/task-create-dialog/task-create-dialog.component';
import { TaskDetailDrawerComponent } from './components/task-detail-drawer/task-detail-drawer.component';

@Component({
  selector: 'app-tasks',
  standalone: true,
  imports: [CommonModule, PinModalComponent, TaskCardComponent, TaskCreateDialogComponent, TaskDetailDrawerComponent],
  templateUrl: './tasks.component.html',
  styleUrl: './tasks.component.css'
})
export class TasksComponent implements OnInit, OnDestroy {
  private taskService = inject(TaskService);
  private collaboratorService = inject(CollaboratorService);
  private authService = inject(AuthService);
  private router = inject(Router);
  private destroy$ = new Subject<void>();

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
  activeTab: 'personal' | 'assigned_to_me' | 'assigned_by_me' = 'personal';

  ngOnInit() {
    this.collaboratorService.getTeam().subscribe(team => {
      this.team = team;
      const savedId = this.authService.getCurrentCollaboratorId();
      if (savedId) {
        const found = team.find(c => c.id === savedId) ?? null;
        if (found) {
          this.activeCollaborator = found;
          this.startPolling();
        } else {
          this.showCollaboratorPicker = true;
        }
      } else {
        this.showCollaboratorPicker = true;
      }
    });
  }

  selectCollaborator(collab: Collaborator) {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
  }

  onPinValidated() {
    if (!this.pendingCollaborator) return;
    this.activeCollaborator = this.pendingCollaborator;
    this.authService.setCurrentCollaboratorId(this.pendingCollaborator.id!);
    this.showPinModal = false;
    this.showCollaboratorPicker = false;
    this.pendingCollaborator = null;
    this.startPolling();
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
    interval(15000).pipe(
      startWith(0),
      takeUntil(this.destroy$),
      switchMap(() => this.taskService.getTasks(this.activeCollaborator!.id!))
    ).subscribe(data => {
      this.personalTasks = data.personal_tasks;
      this.assignedToMe = data.assigned_to_me;
      this.assignedByMe = data.assigned_by_me;
      this.refreshUnseenCount();
    });
  }

  refreshUnseenCount() {
    if (!this.activeCollaborator) return;
    this.taskService.getUnseenCount(this.activeCollaborator.id!).subscribe(r => {
      this.unseenCount = r.unseen_count;
    });
  }

  onTabChange(tab: 'personal' | 'assigned_to_me' | 'assigned_by_me') {
    this.activeTab = tab;
    if (tab === 'assigned_by_me' && this.unseenCount > 0) {
      this.taskService.markAsSeen(this.activeCollaborator!.id!).subscribe(() => {
        this.unseenCount = 0;
        this.assignedByMe = this.assignedByMe.map(t => ({ ...t, is_completion_seen: true }));
      });
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
        this.taskService.completeTask(task.id).subscribe(() => this.refreshTasks());
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

  goToDashboard() {
    this.router.navigate(['/dashboard']);
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }
}
