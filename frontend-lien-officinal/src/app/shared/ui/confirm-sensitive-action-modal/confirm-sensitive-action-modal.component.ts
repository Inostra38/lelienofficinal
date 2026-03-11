import { Component, Input, Output, EventEmitter, OnChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-confirm-sensitive-action-modal',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './confirm-sensitive-action-modal.component.html',
})
export class ConfirmSensitiveActionModalComponent implements OnChanges {
  /** Description courte de l'action (ex: "Ajouter un collaborateur") */
  @Input() actionLabel = '';
  /** 'pin' = collaborateur actif, 'password' = compte pharmacie */
  @Input() confirmationType: 'pin' | 'password' = 'pin';
  /** Précision sur le PIN attendu (ex: "PIN du titulaire") */
  @Input() hint = '';
  /** Message d'erreur à afficher (vide = pas d'erreur) */
  @Input() errorMessage = '';

  @Output() confirmed = new EventEmitter<string>();
  @Output() cancelled = new EventEmitter<void>();

  value = '';
  showValue = false;

  ngOnChanges() {
    // Réinitialiser le champ à chaque ouverture
    this.value = '';
    this.showValue = false;
  }

  get placeholder(): string {
    return this.confirmationType === 'pin' ? '• • • •' : 'Votre mot de passe';
  }

  get inputType(): string {
    if (this.confirmationType === 'pin') return 'text';
    return this.showValue ? 'text' : 'password';
  }

  onConfirm() {
    if (!this.value.trim()) return;
    this.confirmed.emit(this.value.trim());
  }

  onCancel() {
    this.value = '';
    this.cancelled.emit();
  }
}
