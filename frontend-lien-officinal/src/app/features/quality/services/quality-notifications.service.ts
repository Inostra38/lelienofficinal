import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable, tap } from 'rxjs';
import { environment } from '../../../../environments/environment';

export interface ProcedureNotification {
  id: number;
  procedure_id: number;
  procedure_title: string;
  version_number: number;
  is_read: boolean;
  created_at: string;
}

export interface NotificationsResponse {
  results: ProcedureNotification[];
  unread_count: number;
}

@Injectable({ providedIn: 'root' })
export class QualityNotificationsService {
  private http = inject(HttpClient);
  private base = `${environment.apiUrl}/quality/notifications`;

  private _unreadCount = new BehaviorSubject<number>(0);
  unreadCount$ = this._unreadCount.asObservable();

  load(): Observable<NotificationsResponse> {
    return this.http.get<NotificationsResponse>(`${this.base}/`).pipe(
      tap(res => this._unreadCount.next(res.unread_count))
    );
  }

  markRead(ids: number[]): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.base}/mark-read/`, { ids }).pipe(
      tap(() => {
        const current = this._unreadCount.getValue();
        const decrement = Math.min(current, ids.length);
        this._unreadCount.next(Math.max(0, current - decrement));
      })
    );
  }

  markAllRead(): Observable<{ status: string }> {
    return this.http.post<{ status: string }>(`${this.base}/mark-read/`, {}).pipe(
      tap(() => this._unreadCount.next(0))
    );
  }
}
