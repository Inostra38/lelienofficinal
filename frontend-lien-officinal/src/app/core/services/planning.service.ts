import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';

// ── Interfaces ────────────────────────────────────────────────────────────────

export interface PlanningCollaborator {
  id: number;
  first_name: string;
  last_name: string;
  color: string;
  role: string;
  weekly_hours: number;
}

export interface Shift {
  id: number;
  collaborator: PlanningCollaborator | null;
  collaborator_snapshot: string;
  display_name: string;
  start_datetime: string;   // ISO 8601
  end_datetime: string;
  is_published: boolean;
  is_extra_hour: boolean;
  is_absent: boolean;
  absence_type: 'injustifiee' | 'justifiee' | 'maladie' | 'cp' | 'rcr' | 'sans_solde' | null;
  note: string;
  created_at: string;
  updated_at: string;
}

export interface PharmacyDayStatus {
  id: number;
  date: string;             // YYYY-MM-DD
  status: 'open' | 'closed';
  on_call_day: boolean;
  on_call_night: boolean;
  note: string;
}

export interface ShiftSummary {
  shift_id: number;
  date: string;
  start: string;            // HH:MM
  end: string;
  duration_h: number;
  is_extra_hour: boolean;
  is_published: boolean;
}

export interface DaySummary {
  date: string;
  worked_h: number;
  absence_type: string | null;
}

export interface AbsenceSummary {
  absence_id: number;
  start_date: string;
  end_date: string;
  type: string;
  status: 'pending' | 'approved' | 'rejected';
}

export interface AdjustmentSummary {
  adjustment_id: number;
  date: string;
  type: 'overtime' | 'early_departure';
  actual_time: string;
  reference_time: string;
  duration_minutes: number;
  note: string;
}

export interface TimeAdjustment {
  id: number;
  collaborator: PlanningCollaborator;
  date: string;
  type: 'overtime' | 'early_departure';
  actual_time: string;
  reference_time: string;
  duration_minutes: number;
  shift: number | null;
  note: string;
  declared_by: PlanningCollaborator | null;
  created_at: string;
}

export interface CollaboratorWeekSummary {
  collaborator_id: number;
  full_name: string;
  role: string;
  color: string;
  contract_hours: number;
  planned_h: number;
  extra_h: number;
  extra_h_25: number;
  extra_h_50: number;
  balance_h: number;
  shifts: ShiftSummary[];
  days: DaySummary[];
  absences: AbsenceSummary[];
  adjustments: AdjustmentSummary[];
}

export interface WeekResponse {
  week_start: string;
  week_end: string;
  shifts: Shift[];
  day_statuses: PharmacyDayStatus[];
  summary: CollaboratorWeekSummary[];
  template_letter?: string | null;
  contracts?: Record<number, { start_date: string; end_date: string | null }>;
  on_call_sunday?: boolean;
  on_call_day_start?:   string | null;
  on_call_day_end?:     string | null;
  on_call_night_start?: string | null;
  on_call_night_end?:   string | null;
}

export interface AbsenceRequest {
  id: number;
  collaborator: PlanningCollaborator;
  start_date: string;
  end_date: string;
  type: 'cp' | 'maladie' | 'rcr' | 'sans_solde';
  status: 'pending' | 'approved' | 'rejected';
  note: string;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: PlanningCollaborator | null;
  posted_by_manager: boolean;
}

export interface PlanningSettings {
  draft_window: 2 | 3 | 4;
  on_call_day_start:   string | null;
  on_call_day_end:     string | null;
  on_call_night_start: string | null;
  on_call_night_end:   string | null;
  on_call_sunday: boolean;
}

export interface MonthlyAbsenceEntry {
  collaborator_id: number;
  initials: string;
  color: string;
  type: string;
}

export type MonthlyAbsenceSummary = Record<string, MonthlyAbsenceEntry[]>;

export interface CreateShiftDto {
  collaborator_id: number;
  start_datetime: string;
  end_datetime: string;
  is_extra_hour?: boolean;
  note?: string;
}

export interface CreateAbsenceDto {
  collaborator_id?: number;
  start_date: string;
  end_date: string;
  type?: 'cp' | 'maladie' | 'rcr' | 'sans_solde' | 'justifiee';
  note?: string;
}

export interface OpeningHours {
  id: number;
  day_of_week: number; // 0=Lun … 5=Sam (Dim toujours fermé)
  start_time: string;  // "HH:MM:SS"
  end_time:   string;
}

export interface WeekTemplate {
  letter: 'A' | 'B' | 'C' | 'D';
  apply_from: string | null;
  shifts: TemplateShift[];
}

export interface TemplateShift {
  id: number;
  collaborator: PlanningCollaborator;
  day_of_week: number;
  start_time: string;  // HH:MM:SS
  end_time: string;
  note: string;
}

export interface WeekTemplateList {
  letter: 'A' | 'B' | 'C' | 'D';
  apply_from: string | null;
  shift_count: number;
}

export interface CreateTemplateShiftDto {
  collaborator_id: number;
  day_of_week: number;
  start_time: string;
  end_time: string;
  note?: string;
}

// ── Contraintes planning ───────────────────────────────────────────────────────

export interface ConstraintItem {
  id: number;
  level: 'regulatory' | 'pharmacy' | 'personal';
  collaborator?: number | null;
  collaborator_name?: string | null;
  description: string;
  is_active: boolean;
  order: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface GenerateTemplateResponse {
  message: string;
  template: {
    weeks: Record<string, Array<{
      collaborator_id: number;
      day_of_week: number;
      start_time: string;
      end_time: string;
      note: string;
    }>>;
    violations: Array<{ level: string; description: string }>;
  } | null;
  conversation: ChatMessage[];
}

// ── Paye interfaces ────────────────────────────────────────────────────────────

export interface PayeHeureSup {
  total: number;
  tranche1: number;
  tranche2: number;
}

export interface PayeDetailSemaine {
  week_str: string;
  heures_travaillees: number;
  seuil: number;
  sup_tranche1: number;
  sup_tranche2: number;
  rattachement: string;
  a_cheval: boolean;
}

export interface PayeAnnuel {
  rcr_acquis: number;
  rcr_consomme: number;
  rcr_solde: number;
  rcr_alerte: boolean;
  contingent_consomme: number;
}

export interface PayeCollaborateur {
  id: number;
  nom: string;
  initiales: string;
  role: string;
  is_tns: boolean;
  couleur: string;
  couleur_texte: string;
  weekly_hours: number;
  jours_travailles: number;
  heures_reelles: number;
  heures_contrat: number | null;
  heures_sup_planning: PayeHeureSup | null;
  detail_semaines: PayeDetailSemaine[] | null;
  solde_ajustements: number | null;
  heures_nuit_20: number | null;
  heures_nuit_40: number | null;
  heures_dimanche: number | null;
  heures_formation: number;
  absences_justifiees: number | null;
  absences_injustifiees: number | null;
  cp_poses: number | null;
  annuel: PayeAnnuel | null;
}

export interface PayeTotauxSalaries {
  jours_travailles: number;
  heures_reelles: number;
  heures_sup_planning_total: number;
  solde_ajustements: number;
  heures_nuit_20: number;
  heures_nuit_40: number;
  heures_dimanche: number;
  heures_formation: number;
  absences_justifiees: number;
  absences_injustifiees: number;
  cp_poses: number;
}

export interface PayeSummaryResponse {
  month: string;
  jours_ouvres_mois: number;
  collaborateurs: PayeCollaborateur[];
  totaux_salaries: PayeTotauxSalaries;
}

// ── Analytics interfaces ───────────────────────────────────────────────────────

export interface HoursSummaryRow {
  collaborator_id: number;
  collaborator_name: string;
  role: string;
  total_hours: number;
  contract_hours: number;
  extra_hours: number;
  presence_days: number;
}

export interface AbsencesByType {
  cp: number;
  maladie: number;
  rcr: number;
  sans_solde: number;
}

export interface AbsencesSummary {
  by_type: AbsencesByType;
  by_collaborator: Record<string, AbsencesByType>;
}

export interface CpBalanceRow {
  collaborator_name: string;
  cp_acquired: number;
  cp_used: number;
  cp_balance: number;
}

export interface CoverageData {
  theoretical_hours: number;
  actual_hours: number;
  coverage_rate: number;
}

export interface OnCallSummary {
  day_guards: number;
  night_guards: number;
  total: number;
}

export interface MonthlyEvolutionRow {
  month: number;
  month_label: string;
  total_hours: number;
  absences: number;
}

export interface AnalyticsData {
  period: 'week' | 'month' | 'year';
  date_from: string;
  date_to: string;
  hours_summary: HoursSummaryRow[];
  absences: AbsencesSummary;
  cp_balance: CpBalanceRow[];
  coverage: CoverageData | null;
  on_call: OnCallSummary;
  monthly_evolution?: MonthlyEvolutionRow[];
}

// ── Service ───────────────────────────────────────────────────────────────────

@Injectable({ providedIn: 'root' })
export class PlanningService {
  private http = inject(HttpClient);
  private apiUrl = `${environment.apiUrl}/api/planning`;

  // ── Semaine ───────────────────────────────────────────────────────────────

  getWeek(week: string): Observable<WeekResponse> {
    return this.http.get<WeekResponse>(`${this.apiUrl}/week/`, {
      params: { week },
    });
  }

  // ── Shifts ────────────────────────────────────────────────────────────────

  createShift(dto: CreateShiftDto): Observable<Shift> {
    return this.http.post<Shift>(`${this.apiUrl}/shifts/`, dto);
  }

  updateShift(id: number, dto: Record<string, any>): Observable<Shift> {
    return this.http.patch<Shift>(`${this.apiUrl}/shifts/${id}/`, dto);
  }

  deleteShift(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/shifts/${id}/`);
  }

  publishShift(id: number): Observable<Shift> {
    return this.http.post<Shift>(`${this.apiUrl}/shifts/${id}/publish/`, {});
  }

  publishWeek(week: string): Observable<{ published: number; week_start: string }> {
    return this.http.post<{ published: number; week_start: string }>(
      `${this.apiUrl}/publish-week/`,
      { week }
    );
  }

  unpublishWeek(week: string): Observable<{ unpublished: number; week_start: string }> {
    return this.http.post<{ unpublished: number; week_start: string }>(
      `${this.apiUrl}/unpublish-week/`,
      { week }
    );
  }

  // ── Absences ──────────────────────────────────────────────────────────────

  getAbsences(week?: string): Observable<AbsenceRequest[]> {
    const params: Record<string, string> = week ? { week } : {};
    return this.http.get<AbsenceRequest[]>(`${this.apiUrl}/absences/`, { params });
  }

  createAbsence(dto: CreateAbsenceDto): Observable<{ absences: AbsenceRequest[]; skipped_days: number }> {
    return this.http.post<{ absences: AbsenceRequest[]; skipped_days: number }>(`${this.apiUrl}/absences/`, dto);
  }

  approveAbsence(id: number): Observable<AbsenceRequest> {
    return this.http.post<AbsenceRequest>(`${this.apiUrl}/absences/${id}/approve/`, {});
  }

  rejectAbsence(id: number): Observable<AbsenceRequest> {
    return this.http.post<AbsenceRequest>(`${this.apiUrl}/absences/${id}/reject/`, {});
  }

  // ── Statuts journaliers ───────────────────────────────────────────────────

  getDayStatuses(week?: string): Observable<PharmacyDayStatus[]> {
    const params: Record<string, string> = week ? { week } : {};
    return this.http.get<PharmacyDayStatus[]>(`${this.apiUrl}/day-status/`, { params });
  }

  setDayStatus(date: string, dto: { status?: 'open' | 'closed'; on_call_day?: boolean; on_call_night?: boolean; note?: string }): Observable<PharmacyDayStatus> {
    return this.http.post<PharmacyDayStatus>(`${this.apiUrl}/day-status/`, { date, ...dto });
  }

  deleteDayStatus(date: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/day-status/${date}/`);
  }

  getMonthlyAbsenceSummary(month: string): Observable<MonthlyAbsenceSummary> {
    return this.http.get<MonthlyAbsenceSummary>(`${this.apiUrl}/absences/monthly-summary/`, { params: { month } });
  }

  // ── Paramètres ────────────────────────────────────────────────────────────

  getSettings(): Observable<PlanningSettings> {
    return this.http.get<PlanningSettings>(`${this.apiUrl}/settings/`);
  }

  updateSettings(dto: Partial<PlanningSettings>): Observable<PlanningSettings> {
    return this.http.patch<PlanningSettings>(`${this.apiUrl}/settings/`, dto);
  }

  // ── Templates ─────────────────────────────────────────────────────────────

  getTemplates(): Observable<WeekTemplateList[]> {
    return this.http.get<WeekTemplateList[]>(`${this.apiUrl}/templates/`);
  }

  getTemplate(letter: string): Observable<WeekTemplate> {
    return this.http.get<WeekTemplate>(`${this.apiUrl}/templates/${letter}/`);
  }

  updateTemplate(letter: string, dto: { apply_from?: string | null }): Observable<WeekTemplate> {
    return this.http.patch<WeekTemplate>(`${this.apiUrl}/templates/${letter}/`, dto);
  }

  createTemplateShift(letter: string, dto: CreateTemplateShiftDto): Observable<TemplateShift> {
    return this.http.post<TemplateShift>(`${this.apiUrl}/templates/${letter}/shifts/`, dto);
  }

  updateTemplateShift(letter: string, id: number, dto: Partial<CreateTemplateShiftDto>): Observable<TemplateShift> {
    return this.http.patch<TemplateShift>(`${this.apiUrl}/templates/${letter}/shifts/${id}/`, dto);
  }

  deleteTemplateShift(letter: string, id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/templates/${letter}/shifts/${id}/`);
  }

  bulkReplaceTemplateShifts(letter: string, shifts: CreateTemplateShiftDto[]): Observable<TemplateShift[]> {
    return this.http.post<TemplateShift[]>(`${this.apiUrl}/templates/${letter}/bulk-replace/`, shifts);
  }

  applyTemplate(letter: string, week: string, force = false): Observable<{ created: number; skipped: number; replaced: number; absence_protected: number; day_protected: number; week_start: string; violations: { shift_date: string; collaborator: string; error: string }[] }> {
    return this.http.post<{ created: number; skipped: number; replaced: number; absence_protected: number; day_protected: number; week_start: string; violations: { shift_date: string; collaborator: string; error: string }[] }>(
      `${this.apiUrl}/templates/${letter}/apply/`,
      { week, force }
    );
  }

  // ── Horaires d'ouverture ───────────────────────────────────────────────────

  getOpeningHours(): Observable<OpeningHours[]> {
    return this.http.get<OpeningHours[]>(`${this.apiUrl}/opening-hours/`);
  }

  createOpeningHours(dto: { day_of_week: number; start_time: string; end_time: string }): Observable<OpeningHours> {
    return this.http.post<OpeningHours>(`${this.apiUrl}/opening-hours/`, dto);
  }

  deleteOpeningHours(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/opening-hours/${id}/`);
  }

  // ── Ajustements horaires ───────────────────────────────────────────────────

  getAdjustments(week: string): Observable<TimeAdjustment[]> {
    return this.http.get<TimeAdjustment[]>(`${this.apiUrl}/adjustments/`, { params: { week } });
  }

  createAdjustment(data: any): Observable<TimeAdjustment> {
    return this.http.post<TimeAdjustment>(`${this.apiUrl}/adjustments/`, data);
  }

  deleteAdjustment(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/adjustments/${id}/`);
  }

  getShiftsForDay(collaboratorId: number, date: string, weekData: WeekResponse): Shift[] {
    return weekData.shifts.filter(s =>
      s.collaborator?.id === collaboratorId && s.start_datetime.startsWith(date)
    );
  }

  // ── Analytics ──────────────────────────────────────────────────────────────

  getAnalytics(period: 'week' | 'month' | 'year', date: string): Observable<AnalyticsData> {
    return this.http.get<AnalyticsData>(`${this.apiUrl}/analytics/`, {
      params: { period, date },
    });
  }

  getPayeSummary(month: string): Observable<PayeSummaryResponse> {
    return this.http.get<PayeSummaryResponse>(`${this.apiUrl}/analytics/paie/?month=${month}`);
  }

  // ── Contraintes planning ───────────────────────────────────────────────────

  getConstraints(): Observable<ConstraintItem[]> {
    return this.http.get<ConstraintItem[]>(`${this.apiUrl}/constraints/`);
  }

  addConstraint(data: { level: string; description: string; collaborator_id?: number }): Observable<ConstraintItem> {
    return this.http.post<ConstraintItem>(`${this.apiUrl}/constraints/`, data);
  }

  updateConstraint(id: number, data: Partial<ConstraintItem>): Observable<ConstraintItem> {
    return this.http.patch<ConstraintItem>(`${this.apiUrl}/constraints/${id}/`, data);
  }

  deleteConstraint(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/constraints/${id}/`);
  }

  generateTemplate(rotation: number, conversation: ChatMessage[]): Observable<GenerateTemplateResponse> {
    return this.http.post<GenerateTemplateResponse>(`${this.apiUrl}/constraints/generate/`, { rotation, conversation });
  }
}
