import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../../environments/environment';
import { ProcedureAttachment } from '../models/procedure.model';

@Injectable({ providedIn: 'root' })
export class AttachmentService {
  private http = inject(HttpClient);
  private api = `${environment.apiUrl}/api/quality`;

  upload(procedureId: number, file: File): Observable<ProcedureAttachment> {
    const fd = new FormData();
    fd.append('file', file);
    fd.append('filename', file.name);
    return this.http.post<ProcedureAttachment>(
      `${this.api}/procedures/${procedureId}/attachments/`, fd,
    );
  }

  delete(attachmentId: number): Observable<void> {
    return this.http.delete<void>(`${this.api}/attachments/${attachmentId}/`);
  }
}
