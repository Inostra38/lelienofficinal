import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './header.component.html',
  styleUrl: './header.component.css'
})
export class HeaderComponent {
  @Input() pharmacyName = '';

  @Output() searchChange = new EventEmitter<string>();
  @Output() logoutClick = new EventEmitter<void>();

  searchTerm = '';

  onSearch() {
    this.searchChange.emit(this.searchTerm);
  }
}
