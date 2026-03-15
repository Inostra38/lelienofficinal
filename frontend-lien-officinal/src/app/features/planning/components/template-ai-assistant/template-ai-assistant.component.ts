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
  @Output() templateGenerated  = new EventEmitter<any>();
  @Output() previewRequested   = new EventEmitter<any>();
  @Output() closed             = new EventEmitter<void>();

  @ViewChild('chatContainer') chatContainer!: ElementRef;

  private planningService = inject(PlanningService);

  conversation: ChatMessage[] = [];
  userInput = '';
  isLoading = false;
  currentTemplate: any = null;
  private shouldScrollToBottom = false;

  readonly rotations = [
    { value: 2, label: 'A/B' },
    { value: 3, label: 'A/B/C' },
    { value: 4, label: 'A/B/C/D' },
  ];

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
