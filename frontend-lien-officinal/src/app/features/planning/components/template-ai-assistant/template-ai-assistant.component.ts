import {
  Component, Input, Output, EventEmitter, inject, ViewChild, ElementRef,
  AfterViewChecked, OnDestroy, OnInit, computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { PlanningService, ChatMessage } from '../../../../core/services/planning.service';
import { Collaborator } from '../../../../core/services/collaborator.service';

@Component({
  selector: 'app-template-ai-assistant',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './template-ai-assistant.component.html',
})
export class TemplateAiAssistantComponent implements OnInit, AfterViewChecked, OnDestroy {
  @Input() rotation = 2;
  @Input() team: Collaborator[] = [];
  @Input() importing = false;
  @Output() templateGenerated  = new EventEmitter<any>();
  @Output() previewRequested   = new EventEmitter<any>();
  @Output() closed             = new EventEmitter<void>();

  @ViewChild('chatContainer') chatContainer!: ElementRef;

  private planningService = inject(PlanningService);

  private readonly aiTask = this.planningService.aiTask;

  readonly conversation    = computed(() => this.aiTask().conversation);
  readonly isLoading       = computed(() => this.aiTask().status === 'pending');
  readonly errorMessage    = computed(() => this.aiTask().status === 'error' ? this.aiTask().errorDetail : '');
  readonly currentTemplate = computed(() => this.aiTask().template);

  userInput = '';
  elapsedSeconds = 0;
  private displayTimer: ReturnType<typeof setInterval> | null = null;
  private shouldScrollToBottom = false;

  readonly rotations = [
    { value: 2, label: 'A/B' },
    { value: 3, label: 'A/B/C' },
    { value: 4, label: 'A/B/C/D' },
  ];

  ngOnInit() {
    // Reprendre l'affichage si une génération est déjà en cours (retour navigation)
    if (this.aiTask().status === 'pending') {
      this._startDisplayTimer();
    }
  }

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  ngOnDestroy() {
    this._stopDisplayTimer();
  }

  generate(userMessage?: string) {
    const conversation = userMessage
      ? [...this.aiTask().conversation, { role: 'user' as const, content: userMessage }]
      : this.aiTask().conversation;
    this.userInput = '';
    this.elapsedSeconds = 0;
    this._startDisplayTimer();
    this.planningService.startAiGeneration(this.rotation, conversation);
  }

  sendAdjustment() {
    const msg = this.userInput.trim();
    if (!msg || this.isLoading()) return;
    this.generate(msg);
  }

  regenerate() {
    this.planningService.clearAiTask();
    this.elapsedSeconds = 0;
    this.generate();
  }

  importTemplate() {
    if (!this.currentTemplate()) return;
    this.templateGenerated.emit(this.currentTemplate());
  }

  countShifts(): number {
    const t = this.currentTemplate();
    if (!t?.weeks) return 0;
    return Object.values(t.weeks)
      .reduce((acc: number, week: any) => acc + (Array.isArray(week) ? week.length : 0), 0);
  }

  extractText(content: string): string {
    const idx = content.indexOf('```json');
    return (idx === -1 ? content : content.substring(0, idx)).trim();
  }

  private _startDisplayTimer() {
    this._stopDisplayTimer();
    this.displayTimer = setInterval(() => {
      const startedAt = this.aiTask().startedAt;
      this.elapsedSeconds = startedAt ? Math.floor((Date.now() - startedAt) / 1000) : 0;
      if (this.aiTask().status !== 'pending') {
        this._stopDisplayTimer();
        this.shouldScrollToBottom = true;
      }
    }, 1000);
  }

  private _stopDisplayTimer() {
    if (this.displayTimer !== null) {
      clearInterval(this.displayTimer);
      this.displayTimer = null;
    }
  }

  private scrollToBottom() {
    try {
      this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
    } catch {}
  }
}
