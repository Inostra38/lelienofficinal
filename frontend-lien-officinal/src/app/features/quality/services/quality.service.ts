import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { Procedure, ProcedureAttachment, ProcedureImage, ReorderPayload } from '../models/procedure.model';

@Injectable({ providedIn: 'root' })
export class QualityService {
  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/quality`;

  getProcedureTree(): Observable<Procedure[]> {
    return this.http.get<Procedure[]>(`${this.api}/procedures/tree/`);
  }

  getProcedures(): Observable<Procedure[]> {
    return this.http.get<Procedure[]>(`${this.api}/procedures/`);
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

  publishProcedure(id: number): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/${id}/publish/`, {});
  }

  archiveProcedure(id: number): Observable<Procedure> {
    return this.http.post<Procedure>(`${this.api}/procedures/${id}/archive/`, {});
  }

  reorderProcedures(payload: ReorderPayload[]): Observable<any> {
    return this.http.patch(`${this.api}/procedures/reorder/`, payload);
  }

  uploadImage(procedureId: number, file: File): Observable<ProcedureImage> {
    const fd = new FormData();
    fd.append('image', file);
    return this.http.post<ProcedureImage>(`${this.api}/procedures/${procedureId}/images/`, fd);
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
