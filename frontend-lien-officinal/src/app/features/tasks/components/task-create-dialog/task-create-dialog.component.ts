import { Component, Input, Output, EventEmitter, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TaskService, TaskPriority, CreateTaskDto } from '../../../../core/services/task.service';
import { CollaboratorService, Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-task-create-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './task-create-dialog.component.html',
})
export class TaskCreateDialogComponent implements OnInit {
  @Input() mode: 'personal' | 'assigned' = 'personal';
  @Input() currentCollaboratorId!: number;

  @Output() created = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  private taskService = inject(TaskService);
  private collaboratorService = inject(CollaboratorService);

  team: Collaborator[] = [];

  form = {
    title: '',
    description: '',
    priority: 'MEDIUM' as TaskPriority,
    due_date: '',
    assigned_to_id: null as number | null
  };

  isLoading = false;
  errorMessage = '';

  priorities = [
    { value: 'HIGH', label: 'Haute' },
    { value: 'MEDIUM', label: 'Moyenne' },
    { value: 'LOW', label: 'Basse' },
  ];

  ngOnInit() {
    if (this.mode === 'assigned') {
      this.collaboratorService.getTeam().subscribe(team => {
        this.team = team.filter(c => c.id !== this.currentCollaboratorId);
      });
    }
  }

  submit() {
    if (!this.form.title.trim()) {
      this.errorMessage = 'Le titre est obligatoire.';
      return;
    }
    if (this.mode === 'assigned' && !this.form.assigned_to_id) {
      this.errorMessage = 'Veuillez choisir un collaborateur à qui assigner la tâche.';
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    const dto: CreateTaskDto = {
      collaborator_id: this.currentCollaboratorId,
      title: this.form.title.trim(),
      description: this.form.description.trim(),
      priority: this.form.priority,
      due_date: this.form.due_date || null,
    };

    if (this.mode === 'assigned' && this.form.assigned_to_id) {
      dto.assigned_to_id = this.form.assigned_to_id;
    }

    this.taskService.createTask(dto).subscribe({
      next: () => {
        this.isLoading = false;
        this.created.emit();
      },
      error: () => {
        this.errorMessage = 'Erreur lors de la création de la tâche.';
        this.isLoading = false;
      }
    });
  }

  getBgClass(color: string): string {
    return `bg-${color}-500`;
  }

  getInitials(c: Collaborator): string {
    return `${c.first_name.charAt(0)}${c.last_name.charAt(0)}`.toUpperCase();
  }
}
