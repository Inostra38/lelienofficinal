import {
  Component, Input, OnInit, forwardRef, inject,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import { QualityService } from '../../services/quality.service';
import { ProcedureCategory } from '../../models/procedure.model';

@Component({
  selector: 'app-badge-selector',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './badge-selector.component.html',
  styleUrls: ['./badge-selector.component.scss'],
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => BadgeSelectorComponent),
      multi: true,
    },
  ],
})
export class BadgeSelectorComponent implements OnInit, ControlValueAccessor {
  @Input() canCreate = false;

  private qualityService = inject(QualityService);

  categories: ProcedureCategory[] = [];
  selectedIds: number[] = [];
  filter = '';
  creating = false;

  private onChange: (val: number[]) => void = () => {};
  private onTouched: () => void = () => {};

  ngOnInit() {
    this.qualityService.getCategories().subscribe({
      next: (cats) => { this.categories = cats; },
    });
  }

  get filtered(): ProcedureCategory[] {
    const q = this.filter.trim().toLowerCase();
    if (!q) return this.categories;
    return this.categories.filter(c => c.name.toLowerCase().includes(q));
  }

  get showCreateButton(): boolean {
    if (!this.canCreate) return false;
    const q = this.filter.trim();
    if (!q) return false;
    return !this.categories.some(c => c.name.toLowerCase() === q.toLowerCase());
  }

  toggle(id: number) {
    this.selectedIds = this.selectedIds.includes(id)
      ? this.selectedIds.filter(x => x !== id)
      : [...this.selectedIds, id];
    this.onChange(this.selectedIds);
    this.onTouched();
  }

  isSelected(id: number): boolean {
    return this.selectedIds.includes(id);
  }

  createCategory() {
    const name = this.filter.trim();
    if (!name || this.creating) return;
    this.creating = true;
    this.qualityService.createCategory({ name, color: '#2E7D32' }).subscribe({
      next: (cat) => {
        this.categories = [...this.categories, cat];
        this.selectedIds = [...this.selectedIds, cat.id];
        this.onChange(this.selectedIds);
        this.onTouched();
        this.filter = '';
        this.creating = false;
      },
      error: () => { this.creating = false; },
    });
  }

  // ControlValueAccessor
  writeValue(val: number[] | null): void {
    this.selectedIds = val ?? [];
  }

  registerOnChange(fn: (val: number[]) => void): void {
    this.onChange = fn;
  }

  registerOnTouched(fn: () => void): void {
    this.onTouched = fn;
  }

  setDisabledState(): void {}
}
