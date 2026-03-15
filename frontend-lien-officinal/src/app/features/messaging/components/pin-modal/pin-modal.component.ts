import {
  Component, Input, Output, EventEmitter, AfterViewInit,
  ViewChildren, QueryList, ElementRef, inject
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { AuthService } from '../../../../core/auth/auth.service';

@Component({
  selector: 'app-pin-modal',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './pin-modal.component.html',
})
export class PinModalComponent implements AfterViewInit {
  @Input() collaboratorName = '';
  @Input() collaboratorRole = '';
  @Input() collaboratorId!: number;
  @Input() mode: 'switch' | 'unlock' = 'switch';

  @Output() pinValidated = new EventEmitter<void>();
  @Output() cancelled = new EventEmitter<void>();

  @ViewChildren('pinInput') pinInputs!: QueryList<ElementRef<HTMLInputElement>>;

  private authService = inject(AuthService);

  // Tableau uniquement pour *ngFor (les valeurs réelles sont dans le DOM)
  readonly slots = [0, 1, 2, 3];

  error = '';
  submitting = false;
  blocked = false;
  failureCount = 0;
  shake = false;

  get title(): string {
    return this.mode === 'unlock' ? 'Session verrouillée' : 'Changer de profil';
  }

  get subtitle(): string {
    return this.mode === 'unlock'
      ? 'Entrez votre PIN pour reprendre la session'
      : 'Connexion en tant que :';
  }

  ngAfterViewInit(): void {
    setTimeout(() => this.focusInput(0), 50);
  }

  private getInputs(): HTMLInputElement[] {
    return this.pinInputs.map(ref => ref.nativeElement);
  }

  private focusInput(index: number): void {
    this.getInputs()[index]?.focus();
  }

  private getPin(): string {
    return this.getInputs().map(el => el.value).join('');
  }

  onKeyDown(index: number, event: KeyboardEvent): void {
    if (this.submitting || this.blocked) return;

    const key = event.key;
    const inputs = this.getInputs();

    if (key >= '0' && key <= '9') {
      event.preventDefault();
      inputs[index].value = key;

      if (index < 3) {
        this.focusInput(index + 1);
      } else {
        // Dernier chiffre saisi
        this.submit();
      }
    } else if (key === 'Backspace') {
      event.preventDefault();
      if (inputs[index].value) {
        inputs[index].value = '';
      } else if (index > 0) {
        inputs[index - 1].value = '';
        this.focusInput(index - 1);
      }
    }
  }

  onPaste(event: ClipboardEvent): void {
    event.preventDefault();
    if (this.submitting || this.blocked) return;

    const text = event.clipboardData?.getData('text') ?? '';
    const digits = text.replace(/\D/g, '').slice(0, 4);
    if (digits.length !== 4) return;

    const inputs = this.getInputs();
    digits.split('').forEach((d, i) => { inputs[i].value = d; });
    this.submit();
  }

  private submit(): void {
    const pin = this.getPin();
    if (pin.length < 4 || this.submitting || this.blocked) return;

    this.submitting = true;
    this.error = '';

    this.authService.collaboratorLogin(this.collaboratorId, pin).subscribe({
      next: () => {
        this.submitting = false;
        this.pinValidated.emit();
      },
      error: (err: HttpErrorResponse) => {
        this.submitting = false;
        this.handleError(err);
      }
    });
  }

  private handleError(err: HttpErrorResponse): void {
    if (err.status === 429) {
      this.error = 'Trop de tentatives, réessayez dans quelques minutes.';
      this.blocked = true;
      return;
    }

    this.failureCount++;

    if (this.failureCount >= 5) {
      this.error = 'Trop de tentatives, réessayez dans 5 minutes.';
      this.blocked = true;
      return;
    }

    this.error = 'Code PIN incorrect.';
    this.shake = true;
    setTimeout(() => { this.shake = false; }, 500);

    const inputs = this.getInputs();
    inputs.forEach(el => { el.value = ''; });
    setTimeout(() => this.focusInput(0), 50);
  }

  trackBySlot(index: number): number { return index; }
}
