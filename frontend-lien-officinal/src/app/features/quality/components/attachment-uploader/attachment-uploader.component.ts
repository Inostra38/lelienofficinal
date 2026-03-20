import {
  Component, Input, OnChanges, SimpleChanges, forwardRef, inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { Observable, forkJoin, of, tap } from 'rxjs';
import { AttachmentService } from '../../services/attachment.service';
import { ProcedureAttachment } from '../../models/procedure.model';

const IMAGE_EXTS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp']);
const DOC_EXTS   = new Set(['pdf', 'doc', 'docx', 'xls', 'xlsx']);
const MAX_SIZE   = 10 * 1024 * 1024; // 10 Mo

interface PendingFile {
  file: File;
  preview: string | null; // data URL pour les images
  fileType: 'image' | 'document';
}

function ext(name: string): string {
  return name.split('.').pop()?.toLowerCase() ?? '';
}

@Component({
  selector: 'app-attachment-uploader',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './attachment-uploader.component.html',
  styleUrls: ['./attachment-uploader.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => AttachmentUploaderComponent),
      multi: true,
    },
  ],
})
export class AttachmentUploaderComponent implements ControlValueAccessor, OnChanges {
  @Input() procedureId: number | null = null;
  @Input() set initialAttachments(val: ProcedureAttachment[]) {
    if (val?.length) { this.uploaded = val; }
  }

  private attachmentService = inject(AttachmentService);

  // Fichiers uploadés côté serveur (connus)
  uploaded: ProcedureAttachment[] = [];
  // Fichiers en attente d'upload (mode création)
  pending: PendingFile[] = [];

  isDragOver = false;
  sizeError = '';

  private onChange: (val: ProcedureAttachment[]) => void = () => {};
  private onTouched: () => void = () => {};

  // Quand procedureId passe de null → valeur : upload les fichiers en attente
  ngOnChanges(changes: SimpleChanges) {
    if (changes['procedureId'] && this.procedureId !== null && this.pending.length > 0) {
      this.flushPending(this.procedureId).subscribe();
    }
  }

  // ── Drag & Drop ─────────────────────────────────────────────────────────

  onDragOver(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave() {
    this.isDragOver = false;
  }

  onDrop(e: DragEvent) {
    e.preventDefault();
    this.isDragOver = false;
    const files = Array.from(e.dataTransfer?.files ?? []);
    this.handleFiles(files);
  }

  onFileInput(e: Event) {
    const files = Array.from((e.target as HTMLInputElement).files ?? []);
    this.handleFiles(files);
    (e.target as HTMLInputElement).value = '';
  }

  // ── Traitement fichiers ──────────────────────────────────────────────────

  private handleFiles(files: File[]) {
    this.sizeError = '';
    for (const file of files) {
      const fileExt = ext(file.name);
      const isImage = IMAGE_EXTS.has(fileExt);
      const isDoc   = DOC_EXTS.has(fileExt);
      if (!isImage && !isDoc) continue; // format non supporté — ignoré silencieusement

      if (file.size > MAX_SIZE) {
        this.sizeError = `"${file.name}" dépasse la limite de 10 Mo.`;
        continue;
      }

      const fileType: 'image' | 'document' = isImage ? 'image' : 'document';
      const pending: PendingFile = { file, preview: null, fileType };

      if (isImage) {
        const reader = new FileReader();
        reader.onload = (ev) => { pending.preview = ev.target?.result as string; };
        reader.readAsDataURL(file);
      }

      if (this.procedureId !== null) {
        // Mode édition : upload immédiat
        this.uploadOne(pending, this.procedureId);
      } else {
        // Mode création : mise en attente
        this.pending = [...this.pending, pending];
      }
    }
    this.onTouched();
  }

  private uploadOne(pending: PendingFile, procedureId: number) {
    this.attachmentService.upload(procedureId, pending.file).subscribe({
      next: (att) => {
        this.uploaded = [...this.uploaded, att];
        this.emit();
      },
    });
  }

  // Upload de tous les fichiers en attente (appelé depuis le parent ou via ngOnChanges)
  flushPending(procedureId: number): Observable<ProcedureAttachment[]> {
    if (this.pending.length === 0) return of([]);
    const uploads = this.pending.map(p =>
      this.attachmentService.upload(procedureId, p.file),
    );
    return forkJoin(uploads).pipe(
      tap((results) => {
        this.uploaded = [...this.uploaded, ...results];
        this.pending = [];
        this.emit();
      }),
    );
  }

  // ── Suppression ──────────────────────────────────────────────────────────

  removeUploaded(att: ProcedureAttachment) {
    this.attachmentService.delete(att.id).subscribe({
      next: () => {
        this.uploaded = this.uploaded.filter(a => a.id !== att.id);
        this.emit();
      },
    });
  }

  removePending(index: number) {
    this.pending = this.pending.filter((_, i) => i !== index);
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  docIcon(name: string): string {
    const e = ext(name);
    if (e === 'pdf') return 'PDF';
    if (e === 'doc' || e === 'docx') return 'DOC';
    if (e === 'xls' || e === 'xlsx') return 'XLS';
    return 'FILE';
  }

  docBgClass(name: string): string {
    const e = ext(name);
    if (e === 'pdf') return 'bg-red-50 border-red-200';
    if (e === 'doc' || e === 'docx') return 'bg-blue-50 border-blue-200';
    if (e === 'xls' || e === 'xlsx') return 'bg-green-50 border-green-200';
    return 'bg-gray-50 border-gray-200';
  }

  docTextClass(name: string): string {
    const e = ext(name);
    if (e === 'pdf') return 'text-red-500';
    if (e === 'doc' || e === 'docx') return 'text-blue-500';
    if (e === 'xls' || e === 'xlsx') return 'text-green-600';
    return 'text-gray-500';
  }

  private emit() {
    this.onChange(this.uploaded);
  }

  // ControlValueAccessor
  writeValue(val: ProcedureAttachment[] | null): void {
    this.uploaded = val ?? [];
  }

  registerOnChange(fn: (val: ProcedureAttachment[]) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(): void {}
}
