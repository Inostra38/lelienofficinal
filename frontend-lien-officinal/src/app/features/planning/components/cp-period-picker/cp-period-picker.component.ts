import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges } from '@angular/core';
import { CommonModule } from '@angular/common';
import { computeCpDays, getJoursFeries } from '../../../../core/utils/date.utils';

export interface CpPeriodValue {
  startPeriod: 'morning' | 'afternoon';
  endPeriod:   'morning' | 'evening';
  workingDays: number;
}

interface TimelineDay {
  iso:    string;
  dayNum: string;
  label:  string;
  bg:     string;
}

function isoDate(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

@Component({
  selector: 'app-cp-period-picker',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './cp-period-picker.component.html',
})
export class CpPeriodPickerComponent implements OnChanges {
  @Input() startDate: string | null = null;
  @Input() endDate:   string | null = null;

  @Output() periodChange = new EventEmitter<CpPeriodValue>();

  startPeriod: 'morning' | 'afternoon' = 'morning';
  endPeriod:   'morning' | 'evening'   = 'evening';
  workingDays = 0;
  impossible  = false;
  timelineDays: TimelineDay[] = [];

  ngOnChanges(_: SimpleChanges) {
    this._compute();
  }

  setStartPeriod(p: 'morning' | 'afternoon') {
    this.startPeriod = p;
    this._compute();
  }

  setEndPeriod(p: 'morning' | 'evening') {
    this.endPeriod = p;
    this._compute();
  }

  private _compute() {
    if (!this.startDate || !this.endDate) {
      this.workingDays  = 0;
      this.impossible   = false;
      this.timelineDays = [];
      this.periodChange.emit({ startPeriod: this.startPeriod, endPeriod: this.endPeriod, workingDays: 0 });
      return;
    }

    const start = new Date(this.startDate + 'T00:00:00');
    const end   = new Date(this.endDate   + 'T00:00:00');

    this.impossible = (
      this.startPeriod === 'afternoon' &&
      this.endPeriod   === 'morning'   &&
      this.startDate   === this.endDate
    );

    this.workingDays = this.impossible
      ? 0
      : computeCpDays(start, end, this.startPeriod, this.endPeriod);

    this._buildTimeline(start, end);
    this.periodChange.emit({
      startPeriod: this.startPeriod,
      endPeriod:   this.endPeriod,
      workingDays: this.workingDays,
    });
  }

  private _buildTimeline(start: Date, end: Date) {
    const diffDays = Math.round((end.getTime() - start.getTime()) / 86400000) + 1;
    if (diffDays > 14) {
      this.timelineDays = [];
      return;
    }

    // Collecte des fériés
    const years = new Set<number>();
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) years.add(d.getFullYear());
    const ferieSet = new Set<string>();
    for (const y of years) {
      for (const f of getJoursFeries(y)) ferieSet.add(isoDate(f));
    }

    // Premier et dernier jour ouvré
    let firstWorking = '';
    let lastWorking  = '';
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const iso = isoDate(d);
      if (d.getDay() !== 0 && !ferieSet.has(iso)) {
        if (!firstWorking) firstWorking = iso;
        lastWorking = iso;
      }
    }

    const BLUE_FULL  = '#bfdbfe';
    const BLUE_RIGHT = `linear-gradient(to right, #e5e7eb 50%, ${BLUE_FULL} 50%)`;
    const BLUE_LEFT  = `linear-gradient(to right, ${BLUE_FULL} 50%, #e5e7eb 50%)`;
    const GRAY       = '#f3f4f6';
    const RED        = '#fecaca';
    const DAY_NAMES  = ['Di', 'Lu', 'Ma', 'Me', 'Je', 'Ve', 'Sa'];

    this.timelineDays = [];
    for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
      const iso       = isoDate(d);
      const isWorking = d.getDay() !== 0 && !ferieSet.has(iso);
      let bg: string;

      if (!isWorking) {
        bg = GRAY;
      } else {
        const isFirst    = iso === firstWorking;
        const isLast     = iso === lastWorking;
        const startCut   = isFirst && this.startPeriod === 'afternoon';
        const endCut     = isLast  && this.endPeriod   === 'morning';
        if      (startCut && endCut) bg = RED;
        else if (startCut)           bg = BLUE_RIGHT;
        else if (endCut)             bg = BLUE_LEFT;
        else                         bg = BLUE_FULL;
      }

      this.timelineDays.push({
        iso,
        dayNum: DAY_NAMES[d.getDay()],
        label:  d.toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'short' }),
        bg,
      });
    }
  }
}
