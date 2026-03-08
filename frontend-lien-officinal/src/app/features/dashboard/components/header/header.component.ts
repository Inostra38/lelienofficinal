import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms'; // <--- INDISPENSABLE pour ngModel

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule], // <--- VÉRIFIE QU'IL EST LÀ
  templateUrl: './header.component.html',
  styleUrl: './header.component.css'
})
export class HeaderComponent {
  @Input() pharmacyName = '';
  @Input() team: any[] = [];
  @Input() activeCollaborator: any | null = null;

  // C'est lui le téléphone
  @Output() searchChange = new EventEmitter<string>(); 
  @Output() sessionClick = new EventEmitter<any>();

  searchTerm: string = '';

  onSearch() {
    // On crie au parent : "Eh ! Le texte a changé !"
    this.searchChange.emit(this.searchTerm);
  }
}