import { Injectable, NgZone } from '@angular/core';
import { Subject, fromEvent, merge, Subscription } from 'rxjs';
import { debounceTime } from 'rxjs/operators';

@Injectable({ providedIn: 'root' })
export class InactivityService {
  private readonly TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

  private locked$ = new Subject<void>();
  private activitySub: Subscription | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(private ngZone: NgZone) {}

  startWatching(): void {
    this.resetTimer();

    // Écoute les événements d'activité utilisateur — au max 1 par seconde
    this.ngZone.runOutsideAngular(() => {
      const activity$ = merge(
        fromEvent(document, 'mousemove'),
        fromEvent(document, 'keydown'),
        fromEvent(document, 'click'),
        fromEvent(document, 'scroll'),
        fromEvent(document, 'touchstart'),
      ).pipe(debounceTime(1000));

      this.activitySub = activity$.subscribe(() => {
        this.ngZone.run(() => this.resetTimer());
      });
    });
  }

  stopWatching(): void {
    this.activitySub?.unsubscribe();
    this.activitySub = null;
    if (this.timer) {
      clearTimeout(this.timer);
      this.timer = null;
    }
  }

  resetTimer(): void {
    if (this.timer) clearTimeout(this.timer);
    this.timer = setTimeout(() => {
      this.ngZone.run(() => this.locked$.next());
    }, this.TIMEOUT_MS);
  }

  onLocked() {
    return this.locked$.asObservable();
  }
}
