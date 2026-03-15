import {
  Component, Input, Output, EventEmitter, inject, ViewChild, ElementRef, AfterViewChecked
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
export class TemplateAiAssistantComponent implements AfterViewChecked {
  @Input() rotation = 2;
  @Input() team: Collaborator[] = [];
  @Output() templateGenerated = new EventEmitter<any>();
  @Output() closed = new EventEmitter<void>();

  @ViewChild('chatContainer') chatContainer!: ElementRef;

  private planningService = inject(PlanningService);

  conversation: ChatMessage[] = [];
  userInput = '';
  isLoading = false;
  currentTemplate: any = null;
  showPreview = false;
  previewLetter = 'A';
  private shouldScrollToBottom = false;

  readonly rotations = [
    { value: 2, label: 'A/B' },
    { value: 3, label: 'A/B/C' },
    { value: 4, label: 'A/B/C/D' },
  ];

  readonly DAY_NAMES = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'];

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom) {
      this.scrollToBottom();
      this.shouldScrollToBottom = false;
    }
  }

  generate(userMessage?: string) {
    if (userMessage) {
      this.conversation = [...this.conversation, { role: 'user', content: userMessage }];
      this.userInput = '';
    }
    this.isLoading = true;

    this.planningService.generateTemplate(this.rotation, this.conversation).subscribe({
      next: (res) => {
        this.conversation    = res.conversation;
        this.currentTemplate = res.template;
        this.isLoading       = false;
        this.shouldScrollToBottom = true;
        // Auto-ouvre la prévisualisation et sélectionne la première lettre disponible
        const letters = this.getPreviewLetters();
        if (letters.length) {
          this.previewLetter = letters[0];
          this.showPreview = true;
        }
      },
      error: () => { this.isLoading = false; }
    });
  }

  sendAdjustment() {
    const msg = this.userInput.trim();
    if (!msg || this.isLoading) return;
    this.generate(msg);
  }

  importTemplate() {
    if (!this.currentTemplate) return;
    this.templateGenerated.emit(this.currentTemplate);
  }

  countShifts(): number {
    if (!this.currentTemplate?.weeks) return 0;
    return Object.values(this.currentTemplate.weeks)
      .reduce((acc: number, week: any) => acc + (Array.isArray(week) ? week.length : 0), 0);
  }

  // ── Prévisualisation ────────────────────────────────────────────────────────

  getPreviewLetters(): string[] {
    if (!this.currentTemplate?.weeks) return [];
    return Object.keys(this.currentTemplate.weeks)
      .filter(l => Array.isArray(this.currentTemplate.weeks[l]) && this.currentTemplate.weeks[l].length > 0);
  }

  getPreviewShiftsForDay(letter: string, dayOfWeek: number): any[] {
    return (this.currentTemplate?.weeks?.[letter] ?? [])
      .filter((s: any) => s.day_of_week === dayOfWeek);
  }

  getCollabName(id: number): string {
    const c = this.team.find(t => t.id === id);
    return c ? `${c.first_name} ${c.last_name}` : `#${id}`;
  }

  getCollabColor(id: number): string {
    const c = this.team.find(t => t.id === id);
    if (!c) return '#4b5563';
    const palette: Record<string, string> = {
      green: '#15803d', blue: '#1d4ed8', purple: '#7c3aed', red: '#b91c1c',
      orange: '#c2410c', yellow: '#a16207', pink: '#be185d', indigo: '#4338ca',
      teal: '#0f766e', cyan: '#0e7490', gray: '#4b5563',
    };
    return palette[c.color] ?? '#4b5563';
  }

  formatTime(t: string): string { return t.substring(0, 5); }

  /** Extract text before the ```json block */
  extractText(content: string): string {
    const idx = content.indexOf('```json');
    return (idx === -1 ? content : content.substring(0, idx)).trim();
  }

  private scrollToBottom() {
    try {
      this.chatContainer.nativeElement.scrollTop = this.chatContainer.nativeElement.scrollHeight;
    } catch {}
  }
}
