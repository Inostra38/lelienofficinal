import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ResourceCard, Category } from '../../../features/dashboard/dashboard.component'; // Import de l'interface

@Component({
  selector: 'app-add-link-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './add-link-modal.component.html',
  styleUrl: './add-link-modal.component.css'
})
export class AddLinkModalComponent {
  @Input() categories: Category[] = [];
  @Input() library: ResourceCard[] = []; // Liste des Cartes du Catalogue
  
  @Output() close = new EventEmitter<void>();
  @Output() addLink = new EventEmitter<any>();
  @Output() selectCard = new EventEmitter<ResourceCard>(); // 👈 NOUVEL OUTPUT

  step: 'CHOICE' | 'WEB' | 'FILE' | 'CATALOG' = 'CHOICE';
  searchCatalog: string = '';
  
  formData = {
    title: '',
    url: '',
    file: null as File | null,
    type: 'WEB' as 'WEB' | 'PDF',
    category: ''
  };

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.formData.file = input.files[0];
    }
  }

  // 👇 LOGIQUE MODIFIÉE : Émet la carte pour l'assignation
  selectFromCatalog(card: ResourceCard) {
    this.close.emit(); // Ferme la modale principale
    this.selectCard.emit(card); // Envoie la carte au Dashboard
    
    // Réinitialisation
    this.formData = { title: '', url: '', file: null, type: 'WEB', category: '' };
    this.step = 'CHOICE';
  }

  submit() {
    // Logique de soumission pour les liens PERSONNELS (WEB/FILE)
    if (!this.formData.category) {
        alert("Veuillez sélectionner une catégorie.");
        return;
    }
    
    const payload = { 
      category: this.formData.category,
      title: this.formData.title,
    };

    if (this.step === 'WEB') {
      this.addLink.emit({ ...payload, type: 'WEB', url: this.formData.url, file: null });
    } 
    else if (this.step === 'FILE') {
      this.addLink.emit({ ...payload, type: 'FILE', url: '', file: this.formData.file });
    }
  }
}