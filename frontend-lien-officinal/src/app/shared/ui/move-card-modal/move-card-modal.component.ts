import { Component, EventEmitter, HostListener, Input, Output, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Category, ResourceCard } from '../../../features/dashboard/dashboard.component';

@Component({
  selector: 'app-move-card-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './move-card-modal.component.html',
  styleUrls: ['./move-card-modal.component.css']
})
export class MoveCardModalComponent implements OnInit {
  @Input() categories: Category[] = [];
  @Input() card!: ResourceCard;
  @Input() currentCategoryId!: number;
  
  @Output() move = new EventEmitter<number>();
  @Output() cancel = new EventEmitter<void>();

  selectedCategoryId: number | null = null;

  @HostListener('document:keydown.escape')
  onEscape() { this.cancel.emit(); }

  ngOnInit() {
    this.selectedCategoryId = this.currentCategoryId;
  }

  onSubmit() {
    if (this.selectedCategoryId && this.selectedCategoryId !== this.currentCategoryId) {
      this.move.emit(this.selectedCategoryId);
    } else {
      this.cancel.emit();
    }
  }
}