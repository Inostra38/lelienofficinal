import { Component, Input, Output, EventEmitter, HostListener, OnInit, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { QuillModule } from 'ngx-quill';
import { ToastService } from '../../../../core/services/toast.service';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-card-detail',
  standalone: true,
  imports: [CommonModule, FormsModule, QuillModule],
  templateUrl: './card-detail.component.html',
  styleUrls: ['./card-detail.component.css']
})
export class CardDetailComponent implements OnInit {
  @Input() card: any;
  @Output() close = new EventEmitter<void>();
  @Output() cardUpdated = new EventEmitter<any>();

  // Gestion des onglets
  activeTab: 'INFO' | 'NOTES' = 'INFO';

  // Mode édition
  isEditMode = false;

  // Ajout de lien
  showAddForm = false;
  newItem = { label: '', type: 'WEB', url: '', file: null as File | null };

  // Édition des notes
  editableNoteCourte: string = '';
  editableNoteLongue: string = '';

  // Édition de la carte
  editableTitre: string = '';
  editableDescription: string = '';

  // États
  isSaving = false;
  saveSuccess = false;

  readonly quillModules = {
    toolbar: [
      ['bold', 'italic', 'underline'],
      [{ list: 'ordered' }, { list: 'bullet' }],
      ['link'],
      ['clean'],
    ]
  };

  private http: HttpClient = inject(HttpClient);
  private toast: ToastService = inject(ToastService);

  @HostListener('document:keydown.escape')
  onEscape() { this.close.emit(); }

  constructor() {}

  ngOnInit() {
    // Initialiser les champs éditables avec les valeurs actuelles
    this.editableNoteCourte = this.card.note_courte || '';
    this.editableNoteLongue = this.card.note_longue || '';
    this.editableTitre = this.card.titre || '';
    this.editableDescription = this.card.description_officielle || '';
  }

  // ============================================
  // BADGES
  // ============================================

  getBadgeClass(cardType: string): string {
    switch(cardType) {
      case 'PRIVATE': return 'badge-private';
      case 'OFFICIAL': return 'badge-official';
      case 'PARTNER': return 'badge-partner';
      default: return '';
    }
  }

  getBadgeLabel(cardType: string): string {
    switch(cardType) {
      case 'PRIVATE': return 'Privée';
      case 'OFFICIAL': return 'Validé';
      case 'PARTNER': return 'Partenaire';
      default: return '';
    }
  }

  // ============================================
  // MODE ÉDITION
  // ============================================

  canEdit(): boolean {
    if (this.card.type === 'PRIVATE') return true;
    return (this.card.items || []).some((item: any) => item.owner !== null);
  }

  enterEditMode() {
    this.isEditMode = true;
    this.editableTitre = this.card.titre;
    this.editableDescription = this.card.description_officielle || '';
  }

  cancelEdit() {
    this.isEditMode = false;
  }

  canDeleteItem(item: any): boolean {
    if (this.card.type === 'PRIVATE') return true;
    return item.owner !== null;
  }

  // ============================================
  // SUPPRESSION D'ITEM
  // ============================================

  deleteItem(itemId: number) {
    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders().set('Authorization', `Bearer ${token}`);

    this.http.delete(`${environment.apiUrl}/api/items/${itemId}/`, { headers })
      .subscribe({
        next: () => {
          this.card.items = this.card.items.filter((item: any) => item.id !== itemId);
          this.cardUpdated.emit(this.card);
          this.toast.success('Item supprimé avec succès.');
        },
        error: (err) => {
          console.error('Erreur lors de la suppression:', err);
          this.toast.error('Erreur lors de la suppression.');
        }
      });
  }

  // ============================================
  // RÉORDONNANCEMENT
  // ============================================

  moveItemUp(item: any) {
    const index = this.card.items.indexOf(item);
    if (index <= 0) return;

    [this.card.items[index], this.card.items[index - 1]] = 
    [this.card.items[index - 1], this.card.items[index]];

    this.saveItemsOrder();
  }

  moveItemDown(item: any) {
    const index = this.card.items.indexOf(item);
    if (index >= this.card.items.length - 1) return;

    [this.card.items[index], this.card.items[index + 1]] = 
    [this.card.items[index + 1], this.card.items[index]];

    this.saveItemsOrder();
  }

  saveItemsOrder() {
    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders()
      .set('Authorization', `Bearer ${token}`)
      .set('Content-Type', 'application/json');

    const itemsData = this.card.items.map((item: any, index: number) => ({
      id: item.id,
      ordre: index
    }));

    this.http.post(`${environment.apiUrl}/api/items/reorder/`, 
      { items: itemsData }, 
      { headers }
    ).subscribe({
      next: () => {
        console.log('Ordre mis à jour');
        this.cardUpdated.emit(this.card);
      },
      error: (err) => {
        console.error('Erreur lors de la mise à jour de l\'ordre:', err);
        this.toast.error('Erreur lors du réordonnancement.');
      }
    });
  }

  // ============================================
  // SAUVEGARDE DE LA CARTE
  // ============================================

  saveCardChanges() {
    if (this.card.type !== 'PRIVATE') {
      this.toast.warning('Vous ne pouvez modifier que vos cartes privées.');
      return;
    }

    this.isSaving = true;
    this.saveSuccess = false;

    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders().set('Authorization', `Bearer ${token}`);

    const formData = new FormData();
    formData.append('titre', this.editableTitre);
    formData.append('description_officielle', this.editableDescription);

    this.http.patch(`${environment.apiUrl}/api/cards/${this.card.id}/`, formData, { headers })
      .subscribe({
        next: (updatedCard: any) => {
          this.card.titre = updatedCard.titre;
          this.card.description_officielle = updatedCard.description_officielle;
          this.isSaving = false;
          this.isEditMode = false;
          this.cardUpdated.emit(this.card);
          this.toast.success('Modifications enregistrées.');
        },
        error: (err) => {
          console.error('Erreur lors de la sauvegarde:', err);
          this.toast.error('Erreur lors de la sauvegarde.');
          this.isSaving = false;
        }
      });
  }

  // ============================================
  // AJOUT D'ITEM
  // ============================================

  onFileSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.newItem.file = input.files[0];
    }
  }

  addItem() {
    if (!this.newItem.label.trim()) {
      this.toast.warning('Le nom est obligatoire.');
      return;
    }

    if (this.newItem.type === 'WEB' && !this.newItem.url.trim()) {
      this.toast.warning('L\'URL est obligatoire pour un lien web.');
      return;
    }

    if (this.newItem.type === 'PDF' && !this.newItem.file) {
      this.toast.warning('Le fichier PDF est obligatoire.');
      return;
    }

    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders().set('Authorization', `Bearer ${token}`);

    const formData = new FormData();
    formData.append('label', this.newItem.label);
    formData.append('type', this.newItem.type);
    formData.append('card', this.card.id.toString());

    if (this.newItem.type === 'WEB') {
      formData.append('url', this.newItem.url);
    } else if (this.newItem.type === 'PDF' && this.newItem.file) {
      formData.append('file', this.newItem.file);
    }

    this.http.post(`${environment.apiUrl}/api/items/`, formData, { headers })
      .subscribe({
        next: (newItemResponse: any) => {
          this.card.items = this.card.items || [];
          this.card.items.push(newItemResponse);
          this.cardUpdated.emit(this.card);
          this.newItem = { label: '', type: 'WEB', url: '', file: null };
          this.showAddForm = false;
          this.toast.success('Item ajouté avec succès.');
        },
        error: (err) => {
          console.error('Erreur lors de l\'ajout:', err);
          this.toast.error('Erreur lors de l\'ajout de l\'item.');
        }
      });
  }

  // ============================================
  // SAUVEGARDE DES NOTES
  // ============================================

  saveNotes() {
    this.isSaving = true;
    this.saveSuccess = false;

    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders()
      .set('Authorization', `Bearer ${token}`)
      .set('Content-Type', 'application/json');

    const body = {
      note_courte: this.editableNoteCourte,
      note_longue: this.editableNoteLongue
    };

    this.http.patch(`${environment.apiUrl}/api/cards/${this.card.id}/update-notes/`, body, { headers })
      .subscribe({
        next: (response: any) => {
          this.card.note_courte = response.note_courte;
          this.card.note_longue = response.note_longue;
          this.editableNoteCourte = response.note_courte || '';
          this.editableNoteLongue = response.note_longue || '';
          this.isSaving = false;
          this.saveSuccess = true;
          this.cardUpdated.emit(this.card);
          this.toast.success('Notes enregistrées.');
          setTimeout(() => this.saveSuccess = false, 3000);
        },
        error: (err) => {
          console.error('Erreur lors de la sauvegarde des notes:', err);
          this.toast.error('Erreur lors de la sauvegarde des notes.');
          this.isSaving = false;
        }
      });
  }
}