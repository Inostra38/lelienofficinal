import { Directive, ElementRef, forwardRef, Input, OnDestroy, OnInit } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';
import flatpickr from 'flatpickr';
import { French } from 'flatpickr/dist/l10n/fr';
import { Instance } from 'flatpickr/dist/types/instance';

@Directive({
  selector: '[appDatePicker]',
  standalone: true,
  providers: [
    {
      provide: NG_VALUE_ACCESSOR,
      useExisting: forwardRef(() => DatePickerDirective),
      multi: true,
    },
  ],
})
export class DatePickerDirective implements OnInit, OnDestroy, ControlValueAccessor {
  @Input() minDate?: string;
  @Input() maxDate?: string;

  private fp!: Instance;
  private onChange: (val: string) => void = () => {};
  private onTouched: () => void = () => {};

  constructor(private el: ElementRef<HTMLInputElement>) {}

  ngOnInit() {
    this.fp = flatpickr(this.el.nativeElement, {
      locale: French,
      dateFormat: 'Y-m-d',   // format interne / modèle
      altInput: true,
      altFormat: 'd/m/Y',    // format affiché à l'utilisateur
      allowInput: false,
      disableMobile: true,
      minDate: this.minDate,
      maxDate: this.maxDate,
      onReady: (_d: unknown, _s: unknown, fp: Instance) => {
        // Copier les classes Tailwind de l'input original vers l'altInput
        if (fp.altInput) {
          fp.altInput.className = this.el.nativeElement.className;
          fp.altInput.classList.add('cursor-pointer');
        }
      },
      onChange: (dates: Date[]) => {
        const val = dates[0]
          ? dates[0].toISOString().split('T')[0]
          : '';
        this.onChange(val);
        this.onTouched();
      },
    }) as Instance;
  }

  writeValue(val: string | null) {
    if (this.fp) {
      this.fp.setDate(val ?? '', false);
    }
  }

  registerOnChange(fn: (val: string) => void) { this.onChange = fn; }
  registerOnTouched(fn: () => void) { this.onTouched = fn; }

  setDisabledState(disabled: boolean) {
    if (disabled) this.fp?.destroy();
  }

  ngOnDestroy() {
    this.fp?.destroy();
  }
}
