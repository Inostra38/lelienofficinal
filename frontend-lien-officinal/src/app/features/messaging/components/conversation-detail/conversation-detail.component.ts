import {
  Component, Input, Output, EventEmitter,
  OnChanges, OnDestroy, inject,
  ViewChild, ElementRef, SimpleChanges
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { interval, Subscription, switchMap } from 'rxjs';

import { MessagingService, Conversation, Message } from '../../../../core/services/messaging.service';
import { CollaboratorMinimal } from '../../../../core/services/messaging.service';

export interface PendingFile {
  file: File;
  previewUrl: string | null; // null si non-image
  isImage: boolean;
}

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
  @ViewChild('fileInput') fileInput!: ElementRef<HTMLInputElement>;

  private messagingService = inject(MessagingService);

  // ── État ────────────────────────────────────────────────────────────────
  messages: Message[] = [];
  loadingMessages = false;
  sending = false;
  uploadingFiles = false;
  newMessageContent = '';
  pendingFiles: PendingFile[] = [];
  fileError = '';
  showEmojiPicker = false;

  private static readonly ALLOWED_TYPES = [
    'image/jpeg', 'image/png', 'image/gif', 'image/webp',
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  ];
  private static readonly MAX_SIZE = 10 * 1024 * 1024; // 10 Mo

  private pollingSub: Subscription | null = null;

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
      this.stopPolling();
      this.loadMessages();
      this.startPolling();
    }
  }

  ngOnDestroy(): void {
    this.stopPolling();
  }

  // ── Chargement & polling ─────────────────────────────────────────────────

  loadMessages(): void {
    this.loadingMessages = true;
    this.messagingService.getMessages(this.conversation.id).subscribe({
      next: (msgs) => {
        this.messages = msgs;
        this.loadingMessages = false;
        this.scrollToBottom();
      },
      error: () => { this.loadingMessages = false; }
    });
  }

  private startPolling(): void {
    this.pollingSub = interval(5000).pipe(
      switchMap(() => this.messagingService.getMessages(this.conversation.id))
    ).subscribe({
      next: (msgs) => {
        if (msgs.length !== this.messages.length) {
          this.messages = msgs;
          this.scrollToBottom();
          this.messagingService.markAsRead(this.conversation.id).subscribe();
        }
      }
    });
  }

  private stopPolling(): void {
    this.pollingSub?.unsubscribe();
    this.pollingSub = null;
  }

  private scrollToBottom(): void {
    setTimeout(() => {
      this.messagesEnd?.nativeElement?.scrollIntoView({ behavior: 'smooth' });
    }, 50);
  }

  // ── Envoi de message ─────────────────────────────────────────────────────

  sendMessage(): void {
    const content = this.newMessageContent.trim();
    if (!content || this.sending) return;

    this.sending = true;
    this.messagingService.sendMessage(this.conversation.id, content).subscribe({
      next: (msg) => {
        this.messages.push(msg);
        this.newMessageContent = '';
        this.sending = false;
        this.scrollToBottom();

        // Upload des fichiers en attente
        if (this.pendingFiles.length > 0) {
          this.uploadPendingFiles(msg.id);
        }
      },
      error: () => { this.sending = false; }
    });
  }

  onEnter(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.sendMessage();
    }
  }

  // ── Pièces jointes ───────────────────────────────────────────────────────

  onFileSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (!input.files) return;

    this.fileError = '';
    const files = Array.from(input.files);

    for (const file of files) {
      if (file.size > ConversationDetailComponent.MAX_SIZE) {
        this.fileError = `"${file.name}" dépasse la limite de 10 Mo.`;
        input.value = '';
        return;
      }
      if (!ConversationDetailComponent.ALLOWED_TYPES.includes(file.type)) {
        this.fileError = `Type non autorisé : ${file.type || file.name.split('.').pop()}`;
        input.value = '';
        return;
      }
    }

    // Génère les previews pour les images
    files.forEach(file => {
      const isImg = file.type.startsWith('image/');
      const pending: PendingFile = { file, previewUrl: null, isImage: isImg };
      if (isImg) {
        const reader = new FileReader();
        reader.onload = (e) => { pending.previewUrl = e.target?.result as string; };
        reader.readAsDataURL(file);
      }
      this.pendingFiles.push(pending);
    });

    input.value = '';
  }

  removePendingFile(index: number): void {
    this.pendingFiles.splice(index, 1);
    if (this.pendingFiles.length === 0) this.fileError = '';
  }

  private uploadPendingFiles(messageId: string): void {
    const files = [...this.pendingFiles];
    this.pendingFiles = [];
    this.uploadingFiles = true;

    let completed = 0;
    files.forEach(pf => {
      this.messagingService.uploadAttachment(messageId, pf.file).subscribe({
        next: () => {
          completed++;
          if (completed === files.length) {
            this.uploadingFiles = false;
            this.loadMessages();
          }
        },
        error: () => {
          completed++;
          if (completed === files.length) this.uploadingFiles = false;
        }
      });
    });
  }

  downloadAttachment(attachmentId: string, fileName: string): void {
    this.messagingService.downloadAttachment(attachmentId).subscribe({
      next: (blob) => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        a.click();
        URL.revokeObjectURL(url);
      }
    });
  }

  // ── Helpers fichiers ─────────────────────────────────────────────────────

  getFileIcon(fileType: string): string {
    if (fileType.startsWith('image/')) return 'image';
    if (fileType === 'application/pdf') return 'pdf';
    if (fileType.includes('word')) return 'word';
    if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'excel';
    return 'file';
  }

  getFileIconColor(fileType: string): string {
    if (fileType.startsWith('image/')) return 'text-blue-500';
    if (fileType === 'application/pdf') return 'text-red-500';
    if (fileType.includes('word')) return 'text-blue-600';
    if (fileType.includes('excel') || fileType.includes('spreadsheet')) return 'text-green-600';
    return 'text-gray-400';
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

  deleteConversation(): void {
    if (!confirm(`Supprimer le fil "${this.conversation.subject}" ?`)) return;
    this.messagingService.deleteConversation(this.conversation.id).subscribe({
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

  formatFileSize(bytes: number): string {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} Ko`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
  }

  isImage(fileType: string): boolean {
    return fileType.startsWith('image/');
  }

  getParticipantNames(): string {
    return this.conversation.participants.map(p => p.first_name).join(', ');
  }
}
