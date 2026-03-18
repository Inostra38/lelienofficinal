import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

@Injectable({ providedIn: 'root' })
export class DragDropService {
  currentDragId: number | null = null;
  sourceGroupId: number | null = null;
  reload$ = new Subject<number | null>();
}
