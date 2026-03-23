import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Procedure, ProcedureGroup, ProcedureCategory, ProcedureAttachment, ProcedureImage, ReorderPayload } from '../models/procedure.model';

@Injectable({ providedIn: 'root' })
export class QualityService {
  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/quality`;

  // ── ProcedureCategories ──────────────────────────────────────────────────

  getCategories(): Observable<ProcedureCategory[]> {
    return this.http.get<ProcedureCategory[]>(`${this.api}/categories/`);
  }

  createCategory(data: { name: string; color: string }): Observable<ProcedureCategory> {
    return this.http.post<ProcedureCategory>(`${this.api}/categories/`, data);
  }

  // ── ProcedureGroups ──────────────────────────────────────────────────────

  getGroups(): Observable<ProcedureGroup[]> {
    return this.http.get<ProcedureGroup[]>(`${this.api}/groups/`);
  }

  getGroup(id: number): Observable<ProcedureGroup> {
    return this.http.get<ProcedureGroup>(`${this.api}/groups/${id}/`);
  }

  createGroup(data: Partial<ProcedureGroup>): Observable<ProcedureGroup> {
    return this.http.post<ProcedureGroup>(`${this.api}/groups/`, data);
  }

  updateGroup(id: number, data: Partial<ProcedureGroup>): Observable<ProcedureGroup> {
    return this.http.patch<ProcedureGroup>(`${this.api}/groups/${id}/`, data);
  }

  deleteGroup(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/groups/${id}/`);
  }

  // ── Procedures ───────────────────────────────────────────────────────────

  getProceduresForGroup(groupId?: number): Observable<Procedure[]> {
    if (groupId != null) {
      return this.http.get<Procedure[]>(`${this.api}/procedures/?group=${groupId}`);
    }
    return this.http.get<Procedure[]>(`${this.api}/procedures/?group=none`);
  }

  getProcedures(params?: { status?: string }): Observable<Procedure[]> {
    const query = params?.status ? `?status=${params.status}` : '';
    return this.http.get<Procedure[]>(`${this.api}/procedures/${query}`);
  }

  getProcedure(id: number): Observable<Procedure> {
    return this.http.get<Procedure>(`${this.api}/procedures/${id}/`);
  }

  createProcedure(data: Partial<Procedure>): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/`, data);
  }

  updateProcedure(id: number, data: Partial<Procedure>): Observable<Procedure> {
    return this.http.patch<Procedure>(`${this.api}/procedures/${id}/`, data);
  }

  deleteProcedure(id: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/procedures/${id}/`);
  }

  publishProcedure(id: number, changeSummary?: string): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/${id}/publish/`, { change_summary: changeSummary });
  }

  markProcedureRead(id: number): Observable<void> {
    return this.http.post<void>(`${this.api}/procedures/${id}/mark-read/`, {});
  }

  archiveProcedure(id: number): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/${id}/archive/`, {});
  }

  reorderProcedures(payload: ReorderPayload[]): Observable<any> {
    return this.http.patch(`${this.api}/procedures/reorder/`, payload);
  }

  reorderGroups(orderedIds: number[]): Observable<any> {
    return this.http.post(`${this.api}/groups/reorder/`, { order: orderedIds });
  }

  getArchivedProcedures(): Observable<Procedure[]> {
    return this.http.get<Procedure[]>(`${this.api}/procedures/?archived=true`);
  }

  unarchiveProcedure(id: number): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/${id}/unarchive/`, {});
  }

  uploadImage(procedureId: number, file: File): Observable<ProcedureImage> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ProcedureImage>(`${this.api}/procedures/${procedureId}/images/`, fd);
  }

  deleteImage(imageId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/images/${imageId}/`);
  }

  getAttachments(procedureId: number): Observable<ProcedureAttachment[]> {
    return this.http.get<ProcedureAttachment[]>(`${this.api}/procedures/${procedureId}/attachments/`);
  }

  uploadAttachment(procedureId: number, file: File, filename: string): Observable<ProcedureAttachment> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('filename', filename);
    return this.http.post<ProcedureAttachment>(`${this.api}/procedures/${procedureId}/attachments/`, fd);
  }

  deleteAttachment(attachmentId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/attachments/${attachmentId}/`);
  }
}
