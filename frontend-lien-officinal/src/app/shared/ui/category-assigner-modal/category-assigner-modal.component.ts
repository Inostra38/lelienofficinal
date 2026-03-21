import { Component, EventEmitter, HostListener, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Category, ResourceCard } from '../../../features/dashboard/dashboard.component'; // Import de l'interface

@Component({
  selector: 'app-category-assigner-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './category-assigner-modal.component.html',
  styleUrls: ['./category-assigner-modal.component.css']
})
export class CategoryAssignerModalComponent {
  @Input() categories: Category[] = [];
  @Input() cardToAssign!: ResourceCard; // La carte que l'on veut classer
  @Output() assign = new EventEmitter<number>(); // Émet l'ID de la catégorie choisie
  @Output() cancel = new EventEmitter<void>();

  selectedCategoryId: number | null = null;

  @HostListener('document:keydown.escape')
  onEscape() { this.cancel.emit(); }

  onSubmit() {
    if (this.selectedCategoryId) {
      this.assign.emit(this.selectedCategoryId);
    }
  }
}