import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Task, TaskPriority } from '../../../../core/services/task.service';

@Component({
  selector: 'app-task-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './task-card.component.html',
  styleUrl: './task-card.component.css'
})
export class TaskCardComponent {
  @Input() task!: Task;
  @Input() currentCollaboratorId: number | null = null;
  @Input() hasBeenOpened = false;

  @Output() action = new EventEmitter<'start' | 'complete' | 'delete' | 'reopen'>();
  @Output() openDetail = new EventEmitter<Task>();

  get priorityBorderClass(): string {
    const map: Record<TaskPriority, string> = {
      HIGH: 'border-l-red-500',
      MEDIUM: 'border-l-orange-400',
      LOW: 'border-l-green-500'
    };
    return map[this.task.priority];
  }

  get priorityLabel(): string {
    const map: Record<TaskPriority, string> = { HIGH: 'Haute', MEDIUM: 'Moyenne', LOW: 'Basse' };
    return map[this.task.priority];
  }

  get dueDateClass(): string {
    if (!this.task.due_date) return 'text-gray-400';
    const due = new Date(this.task.due_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    due.setHours(0, 0, 0, 0);
    if (due < today) return 'text-red-500 font-semibold';
    if (due.getTime() === today.getTime()) return 'text-orange-500 font-semibold';
    return 'text-gray-400';
  }

  get canDelete(): boolean {
    if (!this.currentCollaboratorId) return false;
    return this.task.created_by?.id === this.currentCollaboratorId;
  }

  get isDone(): boolean { return this.task.status === 'DONE'; }
  get isTodo(): boolean { return this.task.status === 'TODO'; }
  get isInProgress(): boolean { return this.task.status === 'IN_PROGRESS'; }

  getInitials(collab: { first_name: string; last_name: string }): string {
    return `${collab.first_name.charAt(0)}${collab.last_name.charAt(0)}`.toUpperCase();
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  formatDate(date: string): string {
    return new Date(date).toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' });
  }

  onAction(evt: Event, action: 'start' | 'complete' | 'delete' | 'reopen') {
    evt.stopPropagation();
    this.action.emit(action);
  }
}
