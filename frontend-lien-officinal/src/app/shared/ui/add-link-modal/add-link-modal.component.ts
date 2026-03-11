import { Component, EventEmitter, Input, Output, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { ResourceCard, Category } from '../../../features/dashboard/dashboard.component';

interface ResourceItemForm {
  tempId: number;
  type: 'WEB' | 'PDF' | 'TEL' | 'MAIL';
  label: string;
  url: string;
  file: File | null;
}

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
  @Output() categoryCreated = new EventEmitter<void>();
  @Output() resourceCreated = new EventEmitter<void>(); // ✅ NOUVEAU

  step: 'CHOICE' | 'RESOURCE' | 'CATALOG' | 'CATEGORY' = 'CHOICE';
  searchCatalog: string = '';
  
  // ✅ Sections collapsibles
  sectionsOpen = {
    info: true,
    items: true,
    notes: false
  };

  // ✅ Formulaire complet
  resourceForm = {
    titre: '',
    category: '',
    description_courte: '',
    logo: null as File | null,
    note_courte: '',
    note_longue: ''
  };

  // ✅ Liste dynamique d'items
  items: ResourceItemForm[] = [];
  nextItemId = 1;

  // Création de catégorie
  newCategory = { nom: '' };

  // ✅ Toggle sections
  toggleSection(section: 'info' | 'items' | 'notes') {
    this.sectionsOpen[section] = !this.sectionsOpen[section];
  }

  // ✅ Gestion des items
  addItem() {
    this.items.push({
      tempId: this.nextItemId++,
      type: 'WEB',
      label: '',
      url: '',
      file: null
    });
  }

  removeItem(tempId: number) {
    this.items = this.items.filter(item => item.tempId !== tempId);
  }

  onItemFileSelected(event: Event, item: ResourceItemForm) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      item.file = input.files[0];
      if (!item.label) {
        item.label = input.files[0].name;
      }
    }
  }

  onLogoSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.resourceForm.logo = input.files[0];
    }
  }

  // ✅ Validation
  isFormValid(): boolean {
    return !!(
      this.resourceForm.titre.trim() && 
      this.resourceForm.category &&
      this.items.length > 0 &&
      this.items.every(item => {
        if (!item.label.trim()) return false;
        if (item.type === 'WEB' && !item.url.trim()) return false;
        if (item.type === 'PDF' && !item.file) return false;
        if (item.type === 'TEL' && !item.url.trim()) return false;
        if (item.type === 'MAIL' && !item.url.trim()) return false;
        return true;
      })
    );
  }

  // ✅ Soumission complète
  submitResource() {
    if (!this.isFormValid()) {
      alert('Veuillez remplir tous les champs obligatoires');
      return;
    }

    const formData = new FormData();
    
    // Infos générales
    formData.append('titre', this.resourceForm.titre);
    formData.append('category', this.resourceForm.category);
    
    if (this.resourceForm.description_courte) {
      formData.append('description_courte', this.resourceForm.description_courte);
    }
    
    if (this.resourceForm.logo) {
      formData.append('logo', this.resourceForm.logo);
    }

    // Notes
    if (this.resourceForm.note_courte) {
      formData.append('note_courte', this.resourceForm.note_courte);
    }
    
    if (this.resourceForm.note_longue) {
      formData.append('note_longue', this.resourceForm.note_longue);
    }

    // Items (on envoie en JSON stringifié)
    const itemsData = this.items.map((item, index) => ({
      type: item.type,
      label: item.label,
      url: item.type === 'WEB' || item.type === 'TEL' || item.type === 'MAIL' ? item.url : '',
      ordre: index
    }));
    
    formData.append('items', JSON.stringify(itemsData));

    // Fichiers séparés (avec index)
    this.items.forEach((item, index) => {
      if (item.file) {
        formData.append(`item_file_${index}`, item.file);
      }
    });

    // Envoi au backend
    this.http.post('http://127.0.0.1:8000/api/cards/create-full/', formData)
      .subscribe({
        next: () => {
          alert('✅ Ressource créée avec succès !');
          this.resetForm();
          this.resourceCreated.emit(); // ✅ Notifie le parent pour recharger
          this.close.emit();
        },
        error: (err) => {
          console.error('❌ Erreur création ressource:', err);
          alert('Erreur lors de la création. Vérifiez la console.');
        }
      });
  }

  resetForm() {
    this.resourceForm = {
      titre: '',
      category: '',
      description_courte: '',
      logo: null,
      note_courte: '',
      note_longue: ''
    };
    this.items = [];
    this.nextItemId = 1;
    this.step = 'CHOICE';
    this.sectionsOpen = {
      info: true,
      items: true,
      notes: false
    };
  }

  // ============================================================
  // ANCIENNES MÉTHODES (CATALOGUE + CATÉGORIE)
  // ============================================================

  selectFromCatalog(card: ResourceCard) {
    this.close.emit();
    this.selectCard.emit(card);
  }

  createCategory() {
    if (!this.newCategory.nom) return;

    this.http.post('http://127.0.0.1:8000/api/categories/', {
      nom: this.newCategory.nom
    }).subscribe({
      next: () => {
        this.categoryCreated.emit();
        this.close.emit();
        this.newCategory = { nom: '' };
        this.step = 'CHOICE';
      },
      error: (err) => {
        console.error('Erreur création catégorie', err);
        alert(err.error?.nom?.[0] || "Erreur lors de la création.");
      }
    });
  }
}