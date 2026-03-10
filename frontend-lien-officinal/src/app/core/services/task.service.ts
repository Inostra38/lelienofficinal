import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

export type TaskPriority = 'HIGH' | 'MEDIUM' | 'LOW';
export type TaskStatus = 'TODO' | 'IN_PROGRESS' | 'DONE';
export type TaskType = 'PERSONAL' | 'ASSIGNED';

export interface TaskCollaborator {
  id: number;
  first_name: string;
  last_name: string;
  color: string;
}

export interface Task {
  id: string;
  title: string;
  description: string;
  priority: TaskPriority;
  status: TaskStatus;
  type: TaskType;
  created_by: TaskCollaborator;
  assigned_to: TaskCollaborator | null;
  due_date: string | null;
  completed_at: string | null;
  is_completion_seen: boolean;
  order: number;
  created_at: string;
  updated_at: string;
}

export interface TasksResponse {
  personal_tasks: Task[];
  assigned_to_me: Task[];
  assigned_by_me: Task[];
}

export interface CreateTaskDto {
  collaborator_id: number;
  assigned_to_id?: number;
  title: string;
  description?: string;
  priority: TaskPriority;
  due_date?: string | null;
}

@Injectable({ providedIn: 'root' })
export class TaskService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/tasks`;

  private withCollaborator(collaboratorId: number): { headers: HttpHeaders } {
    return { headers: new HttpHeaders({ 'X-Collaborator-Id': String(collaboratorId) }) };
  }

  getTasks(collaboratorId: number): Observable<TasksResponse> {
    return this.http.get<TasksResponse>(`${this.apiUrl}/`, this.withCollaborator(collaboratorId));
  }

  createTask(task: CreateTaskDto): Observable<Task> {
    return this.http.post<Task>(`${this.apiUrl}/`, task);
  }

  updateTask(id: string, updates: Partial<{ title: string; description: string; priority: TaskPriority; due_date: string | null }>, collaboratorId: number): Observable<Task> {
    return this.http.patch<Task>(`${this.apiUrl}/${id}/`, updates, this.withCollaborator(collaboratorId));
  }

  deleteTask(id: string, collaboratorId: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}/`, this.withCollaborator(collaboratorId));
  }

  startTask(id: string): Observable<Task> {
    return this.http.post<Task>(`${this.apiUrl}/${id}/start/`, {});
  }

  completeTask(id: string): Observable<Task> {
    return this.http.post<Task>(`${this.apiUrl}/${id}/complete/`, {});
  }

  reopenTask(id: string): Observable<Task> {
    return this.http.post<Task>(`${this.apiUrl}/${id}/reopen/`, {});
  }

  getUnseenCount(collaboratorId: number): Observable<{ unseen_count: number }> {
    return this.http.get<{ unseen_count: number }>(`${this.apiUrl}/unseen-count/`, this.withCollaborator(collaboratorId));
  }

  markAsSeen(collaboratorId: number): Observable<void> {
    return this.http.post<void>(`${this.apiUrl}/mark-seen/`, {}, this.withCollaborator(collaboratorId));
  }

  reorderTasks(taskIds: string[]): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${this.apiUrl}/reorder/`, { task_ids: taskIds });
  }
}
