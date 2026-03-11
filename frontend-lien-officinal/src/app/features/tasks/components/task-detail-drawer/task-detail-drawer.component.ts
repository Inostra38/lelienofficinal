import { Component, Input, Output, EventEmitter, OnChanges, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService, Task, TaskPriority } from '../../../../core/services/task.service';

@Component({
  selector: 'app-task-detail-drawer',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './task-detail-drawer.component.html',
  styleUrl: './task-detail-drawer.component.css'
})
export class TaskDetailDrawerComponent implements OnChanges {
  @Input() task!: Task;
  @Input() currentCollaboratorId: number | null = null;

  @Output() closed = new EventEmitter<void>();
  @Output() taskUpdated = new EventEmitter<void>();

  private taskService = inject(TaskService);

  editTitle = '';
  editDescription = '';
  editPriority: TaskPriority = 'MEDIUM';
  editDueDate = '';

  isEditing = false;
  isLoading = false;
  errorMessage = '';

  priorities = [
    { value: 'HIGH', label: 'Haute' },
    { value: 'MEDIUM', label: 'Moyenne' },
    { value: 'LOW', label: 'Basse' },
  ];

  ngOnChanges() {
    if (this.task) {
      this.editTitle = this.task.title;
      this.editDescription = this.task.description;
      this.editPriority = this.task.priority;
      this.editDueDate = this.task.due_date || '';
      this.isEditing = false;
    }
  }

  get canEdit(): boolean {
    if (!this.currentCollaboratorId) return false;
    return (
      this.task.created_by?.id === this.currentCollaboratorId ||
      this.task.assigned_to?.id === this.currentCollaboratorId
    );
  }

  get isDone(): boolean { return this.task.status === 'DONE'; }
  get isTodo(): boolean { return this.task.status === 'TODO'; }
  get isInProgress(): boolean { return this.task.status === 'IN_PROGRESS'; }

  get priorityBorderClass(): string {
    const map: Record<TaskPriority, string> = {
      HIGH: 'border-red-500',
      MEDIUM: 'border-orange-400',
      LOW: 'border-green-500'
    };
    return map[this.task.priority];
  }

  get statusLabel(): string {
    const map: Record<string, string> = {
      TODO: 'À faire',
      IN_PROGRESS: 'En cours',
      DONE: 'Terminée'
    };
    return map[this.task.status];
  }

  get statusClass(): string {
    const map: Record<string, string> = {
      TODO: 'bg-gray-100 text-gray-600',
      IN_PROGRESS: 'bg-blue-100 text-blue-700',
      DONE: 'bg-green-100 text-green-700'
    };
    return map[this.task.status];
  }

  getInitials(collab: { first_name: string; last_name: string }): string {
    return `${collab.first_name.charAt(0)}${collab.last_name.charAt(0)}`.toUpperCase();
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' });
  }

  formatDateTime(date: string): string {
    return new Date(date).toLocaleDateString('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  saveEdit() {
    if (!this.editTitle.trim() || !this.currentCollaboratorId) return;
    this.isLoading = true;
    this.taskService.updateTask(
      this.task.id,
      {
        title: this.editTitle.trim(),
        description: this.editDescription.trim(),
        priority: this.editPriority,
        due_date: this.editDueDate || null
      },
      this.currentCollaboratorId
    ).subscribe({
      next: () => {
        this.isLoading = false;
        this.isEditing = false;
        this.taskUpdated.emit();
        this.closed.emit();
      },
      error: () => {
        this.errorMessage = 'Erreur lors de la sauvegarde.';
        this.isLoading = false;
      }
    });
  }

  start() {
    this.taskService.startTask(this.task.id).subscribe(() => {
      this.taskUpdated.emit();
      this.closed.emit();
    });
  }

  complete() {
    this.taskService.completeTask(this.task.id, this.currentCollaboratorId!).subscribe(() => {
      this.taskUpdated.emit();
      this.closed.emit();
    });
  }

  reopen() {
    this.taskService.reopenTask(this.task.id).subscribe(() => {
      this.taskUpdated.emit();
      this.closed.emit();
    });
  }

  delete() {
    if (!this.currentCollaboratorId) return;
    this.taskService.deleteTask(this.task.id, this.currentCollaboratorId).subscribe(() => {
      this.taskUpdated.emit();
      this.closed.emit();
    });
  }
}
