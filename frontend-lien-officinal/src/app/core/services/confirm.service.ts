import { Injectable } from '@angular/core';

export interface ConfirmOptions {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
}

@Injectable({ providedIn: 'root' })
export class ConfirmService {
  visible = false;
  title = '';
  message = '';
  confirmLabel = 'Confirmer';
  danger = true;

  private _resolve!: (v: boolean) => void;

  ask(options: ConfirmOptions): Promise<boolean> {
    this.title        = options.title;
    this.message      = options.message;
    this.confirmLabel = options.confirmLabel ?? 'Confirmer';
    this.danger       = options.danger !== false;
    this.visible      = true;
    return new Promise(resolve => { this._resolve = resolve; });
  }

  confirm() { this.visible = false; this._resolve(true); }
  cancel()  { this.visible = false; this._resolve(false); }
}
