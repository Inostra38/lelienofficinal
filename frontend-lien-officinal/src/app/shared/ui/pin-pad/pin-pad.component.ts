import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';

@Component({
  selector: 'app-pin-pad',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './pin-pad.component.html',
  styleUrl: './pin-pad.component.css'
})
export class PinPadComponent {
  @Input() title: string = 'Entrez votre code';
  @Output() pinComplete = new EventEmitter<string>();
  @Output() cancel = new EventEmitter<void>();

  pin: string = '';
  error: boolean = false;
  keys: (number | string)[] = [1, 2, 3, 4, 5, 6, 7, 8, 9, '', 0, '⌫'];

  onKeyClick(key: number | string) {
    if (key === '') return;
    if (key === '⌫') {
      this.pin = this.pin.slice(0, -1);
      this.error = false;
      return;
    }
    if (this.pin.length < 4) {
      this.pin += key.toString();
      this.error = false;
    }
    if (this.pin.length === 4) {
      setTimeout(() => {
        this.pinComplete.emit(this.pin);
        this.pin = '';
      }, 100);
    }
  }

triggerError() {
    console.log('🔴 Erreur PIN déclenchée dans le composant !'); // Pour le debug
    this.error = true;
    this.pin = ''; // On vide le code visuellement
    
    // On laisse l'erreur active pendant 500ms pour l'animation, 
    // puis on l'enlève pour permettre de retaper
    setTimeout(() => {
      this.error = false;
    }, 1000);
  }
}
