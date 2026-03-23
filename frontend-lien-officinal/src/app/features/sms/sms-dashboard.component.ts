import { Component, OnInit, OnDestroy, ViewChild, ElementRef, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Subject, Subscription, of } from 'rxjs';
import { debounceTime, switchMap, takeUntil } from 'rxjs/operators';

import { SmsService, SmsTemplate, SmsLog, SmsStatus } from '../../core/services/sms.service';
import { PharmacyService, PharmacyData } from '../../core/services/pharmacy.service';
import { CollaboratorService, Collaborator } from '../../core/services/collaborator.service';
import { AuthService } from '../../core/auth/auth.service';
import { ConfirmService } from '../../core/services/confirm.service';
import { PinModalComponent } from '../messaging/components/pin-modal/pin-modal.component';

const GSM7_CHARS =
  '@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ !"#¤%&\'()*+,-./' +
  '0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ' +
  'ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyz' +
  'äöñüà^{}\\\[~]|€';
const GSM7 = new Set([...GSM7_CHARS]);

@Component({
  selector: 'app-sms-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, PinModalComponent],
  templateUrl: './sms-dashboard.component.html',
})
export class SmsDashboardComponent implements OnInit, OnDestroy {
  private smsService = inject(SmsService);
  private pharmacyService = inject(PharmacyService);
  private collaboratorService = inject(CollaboratorService);
  private authService = inject(AuthService);
  private confirmService = inject(ConfirmService);
  private destroy$ = new Subject<void>();
  private subs = new Subscription();
  private patientChange$ = new Subject<void>();

  @ViewChild('messageTextarea') textareaRef!: ElementRef<HTMLTextAreaElement>;
  @ViewChild('templateContentTextarea') templateTextareaRef!: ElementRef<HTMLTextAreaElement>;

  activeTab: 'send' | 'history' | 'templates' = 'send';

  // Data loaded at init
  pharmacy: PharmacyData | null = null;
  team: Collaborator[] = [];
  activeCollaborator: Collaborator | null = null;

  // Collaborator picker / PIN
  showCollaboratorPicker = false;
  pendingCollaborator: Collaborator | null = null;
  showPinModal = false;

  // Templates
  templates: SmsTemplate[] = [];
  selectedTemplateId: number | null = null;

  // Recipient
  recipientCivilite = '';
  recipientPrenom = '';
  recipientNom = '';
  recipientPhone = '';

  // Message
  messageText = '';
  private customVarsInput: Record<string, string> = {};

  // SMS count (client-side)
  smsCount = 0;
  encoding: 'GSM-7' | 'Unicode' = 'GSM-7';

  // Motif
  motif = '';

  // Status
  sending = false;
  successMessage = '';
  errorMessage = '';

  // History
  logs: SmsLog[] = [];
  loadingLogs = false;
  expandedLogId: number | null = null;

  // Templates CRUD
  editingTemplate: SmsTemplate | null = null;
  templateForm = { title: '', content: '' };
  showTemplateForm = false;
  isNewTemplate = false;
  templateSaving = false;
  templateError = '';

  readonly templateContentPlaceholder = 'Bonjour {{patient.civilite}} {{patient.nom}}, votre commande est prête. {{pharmacie.nom}}';

  // Send tab: pharmacie badges → insert REAL value
  readonly pharmacieVarsSend = [
    { field: 'nom_officine', label: 'nom' },
    { field: 'postal_code',  label: 'code postal' },
    { field: 'city',         label: 'ville' },
    { field: 'email',        label: 'email' },
    { field: 'phone',        label: 'téléphone' },
  ];

  // Template editor: pharmacie badges → insert {{variable}}
  readonly pharmacieVarsTemplate = [
    { key: 'pharmacie.nom',        label: 'nom' },
    { key: 'pharmacie.code_postal', label: 'code postal' },
    { key: 'pharmacie.ville',      label: 'ville' },
    { key: 'pharmacie.email',      label: 'email' },
    { key: 'pharmacie.telephone',  label: 'téléphone' },
  ];

  readonly patientVarsTemplate = [
    { key: 'patient.civilite',     label: 'civilité' },
    { key: 'patient.prenom',       label: 'prénom' },
    { key: 'patient.nom',          label: 'nom' },
    { key: 'patient.civilite_nom', label: 'civilité + nom' },
  ];

  readonly expediteurVarsTemplate = [
    { key: 'expediteur.prenom',     label: 'prénom' },
    { key: 'expediteur.prenom_nom', label: 'prénom + initiale' },
    { key: 'expediteur.role',       label: 'poste' },
  ];

  ngOnInit() {
    this.loadTemplates();

    this.pharmacyService.getCurrentPharmacy().pipe(takeUntil(this.destroy$)).subscribe({
      next: (p) => { this.pharmacy = p; }
    });

    this.loadTeam();

    this.patientChange$.pipe(
      debounceTime(400),
      switchMap(() => {
        if (!this.selectedTemplateId) return of(null);
        this.injectPatientVars();
        return this.smsService.preview({
          template_id: this.selectedTemplateId,
          custom_vars: this.customVarsInput,
        });
      }),
      takeUntil(this.destroy$)
    ).subscribe((res) => {
      if (!res) return;
      this.messageText = res.preview_text;
      this.updateSmsCount();
    });
  }

  ngOnDestroy() {
    this.subs.unsubscribe();
    this.destroy$.next();
    this.destroy$.complete();
  }

  // ── Collaborator session ───────────────────────────────────────────────────

  private loadTeam() {
    this.collaboratorService.getTeam().subscribe({
      next: (team) => {
        this.team = team;
        this.subs.add(
          this.authService.collaborator$.subscribe(id => {
            const found = id ? team.find(c => c.id === id) ?? null : null;
            if (!found) {
              this.activeCollaborator = null;
              this.showCollaboratorPicker = true;
              return;
            }
            if (found.id === this.activeCollaborator?.id) return;
            this.showPinModal = false;
            this.pendingCollaborator = null;
            this.activeCollaborator = found;
            this.showCollaboratorPicker = false;
          })
        );
      },
      error: () => { this.showCollaboratorPicker = true; }
    });
  }

  selectCollaborator(collab: Collaborator) {
    this.pendingCollaborator = collab;
    this.showPinModal = true;
    this.showCollaboratorPicker = false;
  }

  onPinValidated() {
    this.showPinModal = false;
    this.pendingCollaborator = null;
  }

  onPinCancelled() {
    this.showPinModal = false;
    this.pendingCollaborator = null;
    if (!this.activeCollaborator) {
      this.showCollaboratorPicker = true;
    }
  }

  changeCollaborator() {
    this.activeCollaborator = null;
    this.authService.clearCurrentCollaborator();
    this.showCollaboratorPicker = true;
  }

  getInitials(collab: Collaborator): string {
    return `${collab.first_name[0]}${collab.last_name[0]}`.toUpperCase();
  }


  // ── Value getters (send tab badges) ───────────────────────────────────────

  getPharmacyValue(field: string): string {
    if (!this.pharmacy) return '';
    return (this.pharmacy as any)[field] ?? '';
  }

  getSenderValue(type: 'prenom' | 'prenom_nom' | 'role'): string {
    const c = this.activeCollaborator;
    if (!c) return '';
    if (type === 'prenom') return c.first_name;
    if (type === 'prenom_nom') return c.last_name ? `${c.first_name} ${c.last_name[0]}.` : c.first_name;
    return c.role;
  }

  getPatientValue(type: 'civilite' | 'prenom' | 'nom' | 'civilite_nom'): string {
    if (type === 'civilite') return this.recipientCivilite;
    if (type === 'prenom') return this.recipientPrenom;
    if (type === 'nom') return this.recipientNom;
    return `${this.recipientCivilite} ${this.recipientNom}`.trim();
  }

  // ── Cursor insertion ──────────────────────────────────────────────────────

  insertAtCursor(value: string): void {
    if (!value) return;
    const el = this.textareaRef.nativeElement;
    el.setRangeText(value, el.selectionStart, el.selectionEnd, 'end');
    this.messageText = el.value;
    el.dispatchEvent(new Event('input'));
    el.focus();
    this.updateSmsCount();
  }

  insertVarInTemplate(variable: string) {
    const el = this.templateTextareaRef.nativeElement;
    const token = `{{${variable}}}`;
    el.setRangeText(token, el.selectionStart, el.selectionEnd, 'end');
    this.templateForm.content = el.value;
    el.focus();
  }

  // ── Template preview ──────────────────────────────────────────────────────

  loadTemplates() {
    this.smsService.getTemplates().subscribe({
      next: (t) => { this.templates = t; }
    });
  }

  onTemplateChange() {
    if (!this.selectedTemplateId) {
      this.customVarsInput = {};
      return;
    }
    this.customVarsInput = {};
    this.callPreview();
  }

  callPreview() {
    if (!this.selectedTemplateId) return;
    this.injectPatientVars();
    this.smsService.preview({
      template_id: this.selectedTemplateId,
      custom_vars: this.customVarsInput,
    }).subscribe({
      next: (res) => {
        this.messageText = res.preview_text;
        this.updateSmsCount();
      }
    });
  }

  onPatientFieldChange() {
    this.patientChange$.next();
  }

  private injectPatientVars() {
    if (this.recipientCivilite) this.customVarsInput['patient.civilite'] = this.recipientCivilite;
    if (this.recipientPrenom) this.customVarsInput['patient.prenom'] = this.recipientPrenom;
    if (this.recipientNom) this.customVarsInput['patient.nom'] = this.recipientNom;
    const cn = `${this.recipientCivilite} ${this.recipientNom}`.trim();
    if (cn) this.customVarsInput['patient.civilite_nom'] = cn;
  }

  onMessageChange() {
    this.updateSmsCount();
  }

  isGsm7(text: string): boolean {
    return [...text].every(c => GSM7.has(c));
  }

  countSms(text: string): number {
    const gsm = this.isGsm7(text);
    const [l1, lN] = gsm ? [160, 153] : [70, 67];
    return text.length <= l1 ? 1 : Math.ceil(text.length / lN);
  }

  updateSmsCount() {
    if (!this.messageText) { this.smsCount = 0; this.encoding = 'GSM-7'; return; }
    this.encoding = this.isGsm7(this.messageText) ? 'GSM-7' : 'Unicode';
    this.smsCount = this.countSms(this.messageText);
  }

  get isPhoneValid(): boolean {
    return this.recipientPhone.replace(/\D/g, '').length >= 10;
  }

  get canSend(): boolean {
    return this.isPhoneValid && this.messageText.trim().length > 0 && !this.sending;
  }

  send() {
    if (!this.canSend) return;
    this.sending = true;
    this.successMessage = '';
    this.errorMessage = '';
    const recipientName = `${this.recipientPrenom} ${this.recipientNom}`.trim();
    this.smsService.send({
      to: this.recipientPhone.replace(/\s/g, ''),
      message: this.messageText,
      ...(this.selectedTemplateId ? { template_id: this.selectedTemplateId } : {}),
      recipient_civilite: this.recipientCivilite,
      recipient_name: recipientName,
      motif: this.motif,
    }).subscribe({
      next: (res) => {
        this.sending = false;
        this.successMessage = `SMS en cours d'envoi — ${res.credits_remaining} crédits restants`;
        this.resetForm();
      },
      error: (err) => {
        this.sending = false;
        const code = err.status;
        if (code === 402) {
          this.errorMessage = err.error?.error || 'Crédits insuffisants';
        } else if (code === 429) {
          this.errorMessage = 'Trop d\'envois — réessayez dans quelques minutes';
        } else {
          this.errorMessage = err.error?.error || 'Erreur lors de l\'envoi';
        }
      }
    });
  }

  statusIcon(s: SmsStatus): string {
    return ({
      PENDING:   '⏳',
      SUCCESS:   '✓',
      DELIVERED: '✓✓',
      FAILED:    '✗',
    } as Record<SmsStatus, string>)[s] ?? '';
  }

  statusClass(s: SmsStatus): string {
    return ({
      PENDING:   'text-amber-500',
      SUCCESS:   'text-green-600',
      DELIVERED: 'text-green-700 font-semibold',
      FAILED:    'text-red-600',
    } as Record<SmsStatus, string>)[s] ?? '';
  }

  private resetForm() {
    this.recipientCivilite = '';
    this.recipientPrenom = '';
    this.recipientNom = '';
    this.recipientPhone = '';
    this.messageText = '';
    this.selectedTemplateId = null;
    this.customVarsInput = {};
    this.motif = '';
    this.smsCount = 0;
    this.encoding = 'GSM-7';
  }

  switchTab(tab: 'send' | 'history' | 'templates') {
    this.activeTab = tab;
    if (tab === 'history') this.loadLogs();
    if (tab === 'templates') this.closeTemplateForm();
  }

  // ── Templates CRUD ────────────────────────────────────────────────────────

  openNewTemplate() {
    this.isNewTemplate = true;
    this.editingTemplate = null;
    this.templateForm = { title: '', content: '' };
    this.templateError = '';
    this.showTemplateForm = true;
  }

  openEditTemplate(t: SmsTemplate) {
    this.isNewTemplate = false;
    this.editingTemplate = t;
    this.templateForm = { title: t.title, content: t.content };
    this.templateError = '';
    this.showTemplateForm = true;
  }

  closeTemplateForm() {
    this.showTemplateForm = false;
    this.editingTemplate = null;
    this.templateForm = { title: '', content: '' };
    this.templateError = '';
  }

  saveTemplate() {
    if (!this.templateForm.title.trim() || !this.templateForm.content.trim()) {
      this.templateError = 'Titre et contenu sont obligatoires.';
      return;
    }
    this.templateSaving = true;
    this.templateError = '';

    const obs = this.isNewTemplate
      ? this.smsService.createTemplate(this.templateForm)
      : this.smsService.updateTemplate(this.editingTemplate!.id, this.templateForm);

    obs.subscribe({
      next: () => {
        this.templateSaving = false;
        this.closeTemplateForm();
        this.loadTemplates();
      },
      error: (err) => {
        this.templateSaving = false;
        this.templateError = err.error?.title?.[0] || err.error?.detail || 'Erreur lors de la sauvegarde.';
      }
    });
  }

  async deleteTemplate(t: SmsTemplate) {
    if (!await this.confirmService.ask({ title: 'Supprimer le template', message: `Supprimer le template "${t.title}" ?`, danger: true })) return;
    this.smsService.deleteTemplate(t.id).subscribe({
      next: () => this.loadTemplates(),
      error: () => {}
    });
  }

  loadLogs() {
    this.loadingLogs = true;
    this.smsService.getLogs().subscribe({
      next: (logs) => { this.logs = logs; this.loadingLogs = false; },
      error: () => { this.loadingLogs = false; }
    });
  }

  toggleLogError(id: number) {
    this.expandedLogId = this.expandedLogId === id ? null : id;
  }

  trackById(_: number, v: { id: number }): number { return v.id; }

  formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit', year: 'numeric' })
      + ' ' + d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' });
  }
}
