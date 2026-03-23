import {
  Component, Input, Output, EventEmitter,
  OnChanges, OnDestroy, inject,
  ViewChild, ElementRef, SimpleChanges
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';

import { MessagingService, Conversation, Message, CollaboratorMinimal } from '../../../../core/services/messaging.service';
import { ConfirmService } from '../../../../core/services/confirm.service';

@Component({
  selector: 'app-conversation-detail',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './conversation-detail.component.html',
})
export class ConversationDetailComponent implements OnChanges, OnDestroy {
  @Input() conversation!: Conversation;
  @Input() activeCollaboratorId: number | null = null;

  @Output() deleted = new EventEmitter<void>();

  @ViewChild('messagesEnd') messagesEnd!: ElementRef;

  private messagingService = inject(MessagingService);
  private confirmService = inject(ConfirmService);
  private destroy$ = new Subject<void>();

  // ── État ────────────────────────────────────────────────────────────────
  messages: Message[] = [];
  loadingMessages = false;
  newMessageContent = '';
  showEmojiPicker = false;

  // Émojis courants pour le picker MVP
  readonly emojis = [
    '😊','😂','👍','❤️','🙏','😍','😢','😮',
    '🎉','👏','🔥','✅','⚠️','📋','💊','🏥',
    '📞','📧','🔍','📁','🗓️','⏰','💡','🚀',
    '👋','😅','🤝','💬','📢','🔔',
  ];

  // ── Cycle de vie ─────────────────────────────────────────────────────────

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['conversation'] && this.conversation) {
      this.destroy$.next(); // déconnecte les souscriptions de la conversation précédente
      this.loadMessages();
      this.connectWebSocket();
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.messagingService.disconnect();
  }

  // ── Chargement initial & WebSocket ───────────────────────────────────────

  loadMessages(): void {
    this.loadingMessages = true;
    this.messagingService.getMessages(this.conversation.id).subscribe({
      next: (msgs) => {
        this.messages = msgs;
        this.loadingMessages = false;
        this.scrollToBottom();
        this.messagingService.markAsRead(this.conversation.id).subscribe();
      },
      error: () => { this.loadingMessages = false; }
    });
  }

  private connectWebSocket(): void {
    this.messagingService.connectToConversation(this.conversation.id);

    this.messagingService.messages$.pipe(
      takeUntil(this.destroy$)
    ).subscribe(message => {
      this.messages.push(message);
      this.scrollToBottom();
      // Marquer comme lu si le message n'est pas le nôtre
      if (message.sender?.id !== this.activeCollaboratorId) {
        this.messagingService.markAsRead(this.conversation.id).subscribe();
      }
    });
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      this.messagesEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  }

  // ── Envoi de message ─────────────────────────────────────────────────────

  sendMessage(): void {
    const content = this.newMessageContent.trim();
    if (!content) return;

    this.messagingService.sendMessage(content);
    this.newMessageContent = '';
  }

  onEnter(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  // ── Émojis ───────────────────────────────────────────────────────────────

  toggleEmojiPicker(): void {
    this.showEmojiPicker = !this.showEmojiPicker;
  }

  insertEmoji(emoji: string): void {
    this.newMessageContent += emoji;
    this.showEmojiPicker = false;
  }

  // ── Suppression du fil ───────────────────────────────────────────────────

  async deleteConversation(): Promise<void> {
    if (!await this.confirmService.ask({ title: 'Supprimer le fil', message: `Supprimer définitivement le fil "${this.conversation.subject}" et tous ses messages ?`, danger: true })) return;
    this.messagingService.deleteConversation(this.conversation.id).subscribe({
      next: () => this.deleted.emit()
    });
  }

  async hideConversation(): Promise<void> {
    if (!await this.confirmService.ask({ title: 'Masquer le fil', message: `Masquer le fil "${this.conversation.subject}" ? Il réapparaîtra si quelqu'un écrit un nouveau message.`, danger: true })) return;
    this.messagingService.hideConversation(this.conversation.id).subscribe({
      next: () => this.deleted.emit()
    });
  }

  // ── Helpers ──────────────────────────────────────────────────────────────

  isMine(msg: Message): boolean {
    return msg.sender?.id === this.activeCollaboratorId;
  }

  getInitials(sender: CollaboratorMinimal): string {
    return `${sender.first_name[0]}${sender.last_name[0]}`.toUpperCase();
  }

  isCreator(): boolean {
    return this.conversation.created_by?.id === this.activeCollaboratorId;
  }

  formatTime(dateStr: string): string {
    return new Date(dateStr).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }

  getParticipantNames(): string {
    return this.conversation.participants.map(p => p.first_name).join(', ');
  }


  getRoleBadgeClass(role: string): string {
    switch (role) {
      case 'Titulaire':   return 'bg-green-100 text-green-800';
      case 'Adjoint':     return 'bg-blue-100 text-blue-800';
      case 'Préparateur': return 'bg-gray-100 text-gray-700';
      case 'Étudiant':    return 'bg-yellow-100 text-yellow-800';
      case 'Apprenti':    return 'bg-orange-100 text-orange-800';
      default:            return 'bg-gray-100 text-gray-700';
    }
  }
}
