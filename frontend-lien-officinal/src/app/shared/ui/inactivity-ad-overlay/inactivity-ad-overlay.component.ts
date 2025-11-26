// inactivity-ad-overlay.component.ts
import { Component, OnInit, OnDestroy, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { InactivityAdService, AdContent } from '../../../core/services/inactivity-ad.service';
import { Subject, takeUntil, combineLatest } from 'rxjs';

@Component({
  selector: 'app-inactivity-ad-overlay',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './inactivity-ad-overlay.component.html',
  styleUrl: './inactivity-ad-overlay.component.css'
})
export class InactivityAdOverlayComponent implements OnInit, OnDestroy {
  private adService = inject(InactivityAdService);
  private destroy$ = new Subject<void>();

  isVisible = false;
  currentAd: AdContent | null = null;

  ngOnInit() {
    combineLatest([
      this.adService.adVisible$,
      this.adService.currentAd
    ]).pipe(
      takeUntil(this.destroy$)
    ).subscribe(([visible, ad]) => {
      console.log('📊 État overlay:', { visible, ad });
      this.isVisible = visible;
      this.currentAd = ad;
    });
  }

  onActivity() {
    // Géré automatiquement par le service
  }

  ngOnDestroy() {
    this.destroy$.next();
    this.destroy$.complete();
  }
}