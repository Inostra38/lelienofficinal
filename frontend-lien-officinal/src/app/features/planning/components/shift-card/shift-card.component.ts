import { Component, Input, Output, EventEmitter, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Shift } from '../../../../core/services/planning.service';
import { ConfirmService } from '../../../../core/services/confirm.service';
import { resolveColor } from '../../../../core/utils/collaborator-colors';

@Component({
  selector: 'app-shift-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './shift-card.component.html',
  styleUrl: './shift-card.component.css',
})
export class ShiftCardComponent {
  private confirmService = inject(ConfirmService);

  @Input() shift!: Shift;
  @Input() isManager = false;

  @Output() publish  = new EventEmitter<number>();
  @Output() delete   = new EventEmitter<number>();

  formatTime(dt: string): string {
    return dt.substring(11, 16);
  }

  get duration(): string {
    const start = new Date(this.shift.start_datetime);
    const end   = new Date(this.shift.end_datetime);
    const h = (end.getTime() - start.getTime()) / 3600000;
    return `${h.toFixed(1).replace('.0', '')}h`;
  }

  get cardStyle(): Record<string, string> {
    if (!this.shift.is_published) return {};
    const c = resolveColor(this.shift.collaborator?.color ?? 'gray');
    return { 'background-color': c.light, 'border-color': c.base, 'color': c.text };
  }

  get isDraft(): boolean { return !this.shift.is_published; }

  get dotColor(): string {
    if (!this.shift.is_published) return '#d1d5db'; // gray-300
    return resolveColor(this.shift.collaborator?.color ?? 'gray').base;
  }

  onPublish(event: MouseEvent) {
    event.stopPropagation();
    this.publish.emit(this.shift.id);
  }

  async onDelete(event: MouseEvent) {
    event.stopPropagation();
    if (await this.confirmService.ask({ title: 'Supprimer le shift', message: 'Supprimer ce shift ?', danger: true })) {
      this.delete.emit(this.shift.id);
    }
  }
}
