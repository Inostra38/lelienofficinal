// src/app/core/services/inactivity-ad.service.ts
import { Injectable } from '@angular/core';
import { BehaviorSubject, fromEvent, merge, timer } from 'rxjs';
import { debounceTime, switchMap, startWith } from 'rxjs/operators';

export interface AdContent {
  id: number;
  image_url: string;
  link_url: string;
  partner_name: string;
}

@Injectable({
  providedIn: 'root'
})
export class InactivityAdService {
  private readonly INACTIVITY_DELAY = 60000;
  
  private showAd$ = new BehaviorSubject<boolean>(false);
  private currentAd$ = new BehaviorSubject<AdContent | null>(null);

  public adVisible$ = this.showAd$.asObservable();
  public currentAd = this.currentAd$.asObservable();

  constructor() {
    this.initActivityDetection();
  }

  private initActivityDetection() {
    const mouseMove$ = fromEvent(document, 'mousemove');
    const mouseClick$ = fromEvent(document, 'click');
    const keyPress$ = fromEvent(document, 'keydown');
    const scroll$ = fromEvent(document, 'scroll', { capture: true });

    const activity$ = merge(mouseMove$, mouseClick$, keyPress$, scroll$);

    activity$.pipe(
      debounceTime(300),
      startWith(null),
      switchMap(() => timer(this.INACTIVITY_DELAY))
    ).subscribe(() => {
      console.log('⏰ Inactivité détectée - Affichage pub');
      this.showAd$.next(true);
    });

    activity$.subscribe(() => {
      if (this.showAd$.value) {
        console.log('👆 Activité détectée - Masquage pub');
        this.hideAd();
      }
    });
  }

  loadAd(ad: AdContent) {
    console.log('📺 Pub chargée:', ad);
    this.currentAd$.next(ad);
  }

  hideAd() {
    this.showAd$.next(false);
  }

  forceShow() {
    console.log('🧪 Affichage forcé de la pub');
    this.showAd$.next(true);
  }
}