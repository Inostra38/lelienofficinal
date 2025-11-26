import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ResourceCard } from '../../dashboard.component';

@Component({
  selector: 'app-card-detail',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './card-detail.component.html',
  styleUrl: './card-detail.component.css'
})
export class CardDetailComponent {
  @Input() card!: ResourceCard;
  @Output() close = new EventEmitter<void>();
  @Output() refreshNeeded = new EventEmitter<void>(); // Événement pour recharger

  private http = inject(HttpClient);

  activeTab: 'INFO' | 'NOTES' = 'INFO';
  
  // Gestion du formulaire d'ajout
  showAddForm = false;
  newItem = { label: '', type: 'WEB', url: '', file: null as File | null };

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.newItem.file = input.files[0];
    }
  }

  addItem() {
    if (!this.newItem.label) return;

    const formData = new FormData();
    formData.append('card', this.card.id.toString());
    formData.append('label', this.newItem.label);
    formData.append('type', this.newItem.type);
    
    if (this.newItem.type === 'WEB') {
      formData.append('url', this.newItem.url);
    } else {
      // Pour les fichiers
      if (this.newItem.file) {
        formData.append('file', this.newItem.file);
      }
    }

    // Appel API
    this.http.post('http://127.0.0.1:8000/api/items/', formData).subscribe({
      next: () => {
        alert('Ressource ajoutée avec succès !');
        this.showAddForm = false;
        // Reset du formulaire
        this.newItem = { label: '', type: 'WEB', url: '', file: null };
        // On demande au parent de recharger les données pour voir le nouveau lien
        this.refreshNeeded.emit();
      },
      error: (err) => {
        console.error(err);
        alert("Erreur lors de l'ajout.");
      }
    });
  }

  saveNotes() {
    console.log("Save notes (Todo)");
  }
}