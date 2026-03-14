import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { Shift } from '../../../../core/services/planning.service';

@Component({
  selector: 'app-shift-card',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './shift-card.component.html',
  styleUrl: './shift-card.component.css',
})
export class ShiftCardComponent {
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

  get cardClasses(): string {
    const color = this.shift.collaborator?.color ?? 'gray';
    if (!this.shift.is_published) {
      return 'bg-white border-dashed border-gray-300 text-gray-500';
    }
    return `bg-${color}-50 border-${color}-300 text-${color}-900`;
  }

  get dotClass(): string {
    const color = this.shift.collaborator?.color ?? 'gray';
    return this.shift.is_published ? `bg-${color}-500` : 'bg-gray-300';
  }

  onPublish(event: MouseEvent) {
    event.stopPropagation();
    this.publish.emit(this.shift.id);
  }

  onDelete(event: MouseEvent) {
    event.stopPropagation();
    if (confirm('Supprimer ce shift ?')) {
      this.delete.emit(this.shift.id);
    }
  }
}
