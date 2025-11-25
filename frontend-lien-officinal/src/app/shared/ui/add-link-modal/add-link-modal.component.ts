import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-add-link-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './add-link-modal.component.html',
  styleUrl: './add-link-modal.component.css'
})
export class AddLinkModalComponent {
  @Input() categories: any[] = []; // <--- NOUVEAU : On reçoit la liste
  @Output() close = new EventEmitter<void>();
  @Output() addLink = new EventEmitter<any>();

  step: 'CHOICE' | 'WEB' | 'FILE' = 'CHOICE';
  
  // On ajoute le champ 'category'
  formData: { title: string; url: string; file: File | null; type: string; category: string } = {
    title: '',
    url: '',
    file: null,
    type: 'WEB',
    category: '' // Vide par défaut
  };

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.formData.file = input.files[0];
    }
  }

  submit() {
    // Validation : On vérifie que la catégorie est choisie
    if (!this.formData.category) {
      alert("Veuillez sélectionner une catégorie.");
      return;
    }

    const payload = { 
      category: this.formData.category, // On l'ajoute à l'envoi
      title: this.formData.title,
      type: this.step
    };

    if (this.step === 'WEB' && this.formData.title && this.formData.url) {
      this.addLink.emit({ ...payload, url: this.formData.url, file: null });
    } 
    else if (this.step === 'FILE' && this.formData.title && this.formData.file) {
      this.addLink.emit({ ...payload, url: '', file: this.formData.file });
    }
  }
}