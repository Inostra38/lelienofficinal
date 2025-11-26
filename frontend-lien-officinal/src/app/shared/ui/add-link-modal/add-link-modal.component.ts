import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ResourceCard, Category } from '../../../features/dashboard/dashboard.component';

@Component({
  selector: 'app-add-link-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './add-link-modal.component.html',
  styleUrl: './add-link-modal.component.css'
})
export class AddLinkModalComponent {
  private http = inject(HttpClient);

  @Input() categories: Category[] = [];
  @Input() library: ResourceCard[] = [];
  
  @Output() close = new EventEmitter<void>();
  @Output() addLink = new EventEmitter<any>();
  @Output() selectCard = new EventEmitter<ResourceCard>();
  @Output() categoryCreated = new EventEmitter<void>(); // ✅ NOUVEAU

  step: 'CHOICE' | 'WEB' | 'FILE' | 'CATALOG' | 'CATEGORY' = 'CHOICE';
  searchCatalog: string = '';
  
  formData = {
    title: '',
    url: '',
    file: null as File | null,
    type: 'WEB' as 'WEB' | 'PDF',
    category: ''
  };

  // ✅ NOUVEAU : Données pour création de catégorie
  newCategory = {
    nom: '',
    icon_slug: '📂'
  };

  availableIcons = ['📂', '⭐', '🏥', '💊', '📦', '🔧', '📋', '🚨', '💼', '🔬', '📞', '🌐'];

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.formData.file = input.files[0];
    }
  }

  selectFromCatalog(card: ResourceCard) {
    this.close.emit();
    this.selectCard.emit(card);
    this.formData = { title: '', url: '', file: null, type: 'WEB', category: '' };
    this.step = 'CHOICE';
  }

  // ✅ NOUVEAU : Créer une catégorie
  createCategory() {
    if (!this.newCategory.nom) return;

    this.http.post('http://127.0.0.1:8000/api/categories/', {
      nom: this.newCategory.nom,
      icon_slug: this.newCategory.icon_slug
    }).subscribe({
      next: () => {
        this.categoryCreated.emit(); // Prévient le parent de recharger
        this.close.emit();
        this.newCategory = { nom: '', icon_slug: '📂' };
        this.step = 'CHOICE';
      },
      error: (err) => {
        console.error('Erreur création catégorie', err);
        alert(err.error?.nom?.[0] || "Erreur lors de la création.");
      }
    });
  }

  submit() {
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