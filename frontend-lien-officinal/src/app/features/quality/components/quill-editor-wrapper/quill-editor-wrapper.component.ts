import {
  Component, Input, Output, EventEmitter, forwardRef, ViewChild,
} from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { QuillModule, QuillEditorComponent } from 'ngx-quill';
import { sanitizeQuillHtml } from '../../../../core/utils/html-sanitizer';

const QUILL_TOOLBAR = [
  ['bold', 'italic', 'underline'],
  [{ header: [1, 2, 3, false] }],
  [{ list: 'ordered' }, { list: 'bullet' }],
  ['link', 'image'],
  ['blockquote', 'code-block'],
  ['clean'],
];

export interface QuillRange {
  index: number;
  length: number;
}

@Component({
  selector: 'app-quill-editor-wrapper',
  standalone: true,
  imports: [CommonModule, FormsModule, QuillModule],
  templateUrl: './quill-editor-wrapper.component.html',
  styleUrls: ['./quill-editor-wrapper.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => QuillEditorWrapperComponent),
      multi: true,
    },
  ],
})
export class QuillEditorWrapperComponent implements ControlValueAccessor {
  @Input() placeholder = 'Rédigez le contenu de la procédure…';
  @Output() contentChange = new EventEmitter<string>();
  @Output() selectionChange = new EventEmitter<QuillRange | null>();

  @ViewChild(QuillEditorComponent) private editorRef!: QuillEditorComponent;

  value = '';
  disabled = false;
  currentRange: QuillRange | null = null;

  readonly modules = { toolbar: QUILL_TOOLBAR };

  private onChange: (val: string) => void = () => {};
  private onTouched: () => void = () => {};

  onEditorChange(event: { html: string | null }): void {
    const html = event.html ?? '';
    this.value = html;
    this.onChange(html);
    this.contentChange.emit(html);
  }

  onSelectionChanged(event: { range: QuillRange | null }): void {
    this.currentRange = event.range?.length ? event.range : null;
    this.selectionChange.emit(this.currentRange);
  }

  onBlur(): void {
    this.onTouched();
  }

  // ── API publique pour le parent ──────────────────────────────────────────

  getSelectedText(): string | null {
    if (!this.currentRange || !this.editorRef?.quillEditor) return null;
    const quill = this.editorRef.quillEditor as any;
    return quill.getText(this.currentRange.index, this.currentRange.length) || null;
  }

  replaceSelection(text: string): void {
    if (!this.currentRange || !this.editorRef?.quillEditor) return;
    const quill = this.editorRef.quillEditor as any;
    quill.deleteText(this.currentRange.index, this.currentRange.length);
    quill.insertText(this.currentRange.index, text);
    this.currentRange = null;
  }

  setFullContent(html: string): void {
    if (!this.editorRef?.quillEditor) return;
    const quill = this.editorRef.quillEditor as any;
    // C4 : purifier avant injection directe dans le DOM (innerHTML). Le contenu
    // peut provenir de l'IA qualité ou d'une source non fiable → XSS stocké.
    const clean = sanitizeQuillHtml(html);
    quill.root.innerHTML = clean;
    this.value = clean;
    this.onChange(clean);
    this.contentChange.emit(clean);
  }

  isEmpty(): boolean {
    return !this.value || this.value.trim() === '' || this.value === '<p><br></p>';
  }

  // ControlValueAccessor
  writeValue(val: string | null): void {
    this.value = val ?? '';
  }

  registerOnChange(fn: (val: string) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(isDisabled: boolean): void {
    this.disabled = isDisabled;
  }
}
