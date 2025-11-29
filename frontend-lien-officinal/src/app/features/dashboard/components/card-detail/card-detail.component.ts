import { Component, Input, Output, EventEmitter, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { environment } from '../../../../../environments/environment';

@Component({
  selector: 'app-card-detail',
  standalone: true,
  imports: [CommonModule, FormsModule],
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
  editableLogo: File | null = null;

  // États
  isSaving = false;
  saveSuccess = false;

  constructor(private http: HttpClient) {}

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
    this.editableLogo = null;
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
          alert('Item supprimé avec succès !');
        },
        error: (err) => {
          console.error('Erreur lors de la suppression:', err);
          alert('Erreur lors de la suppression de l\'item.');
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
        alert('Erreur lors du réordonnancement.');
      }
    });
  }

  // ============================================
  // SAUVEGARDE DE LA CARTE
  // ============================================

  onLogoSelected(event: Event) {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.editableLogo = input.files[0];
    }
  }

  saveCardChanges() {
    if (this.card.type !== 'PRIVATE') {
      alert('Vous ne pouvez modifier que vos cartes privées.');
      return;
    }

    this.isSaving = true;
    this.saveSuccess = false;

    const token = localStorage.getItem('access_token');
    const headers = new HttpHeaders().set('Authorization', `Bearer ${token}`);

    const formData = new FormData();
    formData.append('titre', this.editableTitre);
    formData.append('description_officielle', this.editableDescription);
    if (this.editableLogo) {
      formData.append('logo', this.editableLogo);
    }

    this.http.patch(`${environment.apiUrl}/api/cards/${this.card.id}/`, formData, { headers })
      .subscribe({
        next: (updatedCard: any) => {
          // ✅ MISE À JOUR IMMÉDIATE
          this.card.titre = updatedCard.titre;
          this.card.description_officielle = updatedCard.description_officielle;
          if (updatedCard.logo) {
            this.card.logo = updatedCard.logo;
          }
          
          this.isSaving = false;
          this.isEditMode = false;
          this.cardUpdated.emit(this.card);
          alert('Modifications enregistrées avec succès !');
        },
        error: (err) => {
          console.error('Erreur lors de la sauvegarde:', err);
          alert('Erreur lors de la sauvegarde des modifications.');
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
      alert('Le nom est obligatoire.');
      return;
    }

    if (this.newItem.type === 'WEB' && !this.newItem.url.trim()) {
      alert('L\'URL est obligatoire pour un lien web.');
      return;
    }

    if (this.newItem.type === 'PDF' && !this.newItem.file) {
      alert('Le fichier PDF est obligatoire.');
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
          alert('Item ajouté avec succès !');
        },
        error: (err) => {
          console.error('Erreur lors de l\'ajout:', err);
          alert('Erreur lors de l\'ajout de l\'item.');
        }
      });
  }

  // ============================================
  // SAUVEGARDE DES NOTES (✅ CORRIGÉ)
  // ============================================

  saveNotes() {
    console.log('🔵 saveNotes() appelée !');
    
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

    console.log('📤 Envoi PATCH vers:', `${environment.apiUrl}/api/cards/${this.card.id}/`);
    console.log('📦 Body:', body);

    this.http.patch(`${environment.apiUrl}/api/cards/${this.card.id}/`, body, { headers })
      .subscribe({
        next: (updatedCard: any) => {
          console.log('✅ Réponse reçue:', updatedCard);
          
          // ✅ MISE À JOUR IMMÉDIATE DE LA CARTE LOCALE
          this.card.note_courte = updatedCard.note_courte;
          this.card.note_longue = updatedCard.note_longue;
          
          // ✅ MISE À JOUR DES CHAMPS ÉDITABLES (CRITIQUE!)
          this.editableNoteCourte = updatedCard.note_courte || '';
          this.editableNoteLongue = updatedCard.note_longue || '';
          
          this.isSaving = false;
          this.saveSuccess = true;
          
          // Émettre l'événement pour rafraîchir le dashboard
          this.cardUpdated.emit(updatedCard);
          
          setTimeout(() => this.saveSuccess = false, 3000);
        },
        error: (err) => {
          console.error('❌ Erreur lors de la sauvegarde des notes:', err);
          console.error('Status:', err.status);
          console.error('Message:', err.message);
          alert('Erreur lors de la sauvegarde des notes.');
          this.isSaving = false;
        }
      });
  }
}