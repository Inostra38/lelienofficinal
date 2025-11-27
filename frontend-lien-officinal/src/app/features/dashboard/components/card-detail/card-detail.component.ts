import { Component, EventEmitter, Input, Output, inject, OnInit } from '@angular/core';
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
export class CardDetailComponent implements OnInit {
  @Input() card!: ResourceCard;
  @Output() close = new EventEmitter<void>();
  @Output() refreshNeeded = new EventEmitter<void>();

  private http = inject(HttpClient);

  activeTab: 'INFO' | 'NOTES' = 'INFO';
  
  // Formulaire d'ajout de lien
  showAddForm = false;
  newItem = { label: '', type: 'WEB', url: '', file: null as File | null };

  // Notes éditables (copie locale)
  editableNoteCourte: string = '';
  editableNoteLongue: string = '';

  // États UI
  isSaving = false;
  saveSuccess = false;

  ngOnInit() {
    // Initialiser les valeurs éditables avec les données de la carte
    this.editableNoteCourte = this.card.note_courte || '';
    this.editableNoteLongue = this.card.note_longue || '';
  }

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
      if (this.newItem.file) {
        formData.append('file', this.newItem.file);
      }
    }

    this.http.post('http://127.0.0.1:8000/api/items/', formData).subscribe({
      next: () => {
        this.showAddForm = false;
        this.newItem = { label: '', type: 'WEB', url: '', file: null };
        this.refreshNeeded.emit();
      },
      error: (err) => {
        console.error(err);
        alert("Erreur lors de l'ajout.");
      }
    });
  }

  saveNotes() {
    this.isSaving = true;
    this.saveSuccess = false;

    this.http.patch(`http://127.0.0.1:8000/api/cards/${this.card.id}/update-notes/`, {
      note_courte: this.editableNoteCourte,
      note_longue: this.editableNoteLongue
    }).subscribe({
      next: (response: any) => {
        // Mettre à jour la carte avec les nouvelles valeurs
        this.card.note_courte = response.note_courte;
        this.card.note_longue = response.note_longue;
        
        this.isSaving = false;
        this.saveSuccess = true;
        
        // Cacher le message après 3 secondes
        setTimeout(() => {
          this.saveSuccess = false;
        }, 3000);

        // Notifier le parent pour rafraîchir si nécessaire
        this.refreshNeeded.emit();
      },
      error: (err) => {
        console.error('Erreur sauvegarde notes', err);
        alert("Erreur lors de l'enregistrement des notes.");
        this.isSaving = false;
      }
    });
  }
}