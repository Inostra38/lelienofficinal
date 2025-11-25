import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms'; // Indispensable pour ngModel
import { Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './header.component.html',
  styleUrl: './header.component.css'
})
export class HeaderComponent {
  @Input() team: Collaborator[] = [];
  @Input() activeCollaborator: Collaborator | null = null;

  @Output() searchChange = new EventEmitter<string>(); // Envoie le texte tapé
  @Output() sessionClick = new EventEmitter<Collaborator>(); // Envoie le collab cliqué

  searchTerm: string = '';

  onSearch() {
    this.searchChange.emit(this.searchTerm);
  }
}