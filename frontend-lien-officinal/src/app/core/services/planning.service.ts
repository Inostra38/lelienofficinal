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
  absence_type: 'injustifiee' | 'justifiee' | 'maladie' | 'cp' | 'rcr' | 'sans_solde' | 'formation' | 'conge_exceptionnel' | null;
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
  start_period: 'morning' | 'afternoon';
  end_period:   'morning' | 'evening';
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
  type: 'cp' | 'maladie' | 'rcr' | 'sans_solde' | 'conge_exceptionnel';
  status: 'pending' | 'approved' | 'rejected';
  note: string;
  created_at: string;
  reviewed_at: string | null;
  reviewed_by: PlanningCollaborator | null;
  posted_by_manager: boolean;
  working_days_count: number | null;
  start_period: 'morning' | 'afternoon';
  end_period:   'morning' | 'evening';
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
  type?: 'cp' | 'maladie' | 'rcr' | 'sans_solde' | 'conge_exceptionnel' | 'injustifiee';
  note?: string;
  start_period?: 'morning' | 'afternoon';
  end_period?:   'morning' | 'evening';
}

export interface OpeningHours {
  id: number;
  day_of_week: number; // 0=Lun … 5=Sam (Dim toujours fermé)
  start_time: string;  // "HH:MM:SS"
  end_time:   string;
}

export interface OpeningHoursVersion {
  id: number;
  effective_from: string; // "YYYY-MM-DD" (toujours un lundi)
  slots: OpeningHours[];
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
  heures_shifts: number;
  heures_overtime: number;
  heures_early: number;
  heures_absence_injustifiee: number;
  heures_formation: number;
  total_semaine: number;
  seuil: number;
  sup_tranche1: number;
  sup_tranche2: number;
  heures_dues: number;
  alerte_46h: boolean;
  alerte_10h: boolean;
  jours_alerte_10h: { date: string; heures: number }[];
  alerte_6j: boolean;
  jours_travailles_sem: number;
  rattachement: string;
  a_cheval: boolean;
}

export interface JourFerieDto {
  date: string;
  label: string;
  heures: number;
  premier_mai: boolean;
}

export interface PayeAnnuel {
  rcr_acquis: number;
  rcr_consomme: number;
  rcr_solde: number;
  rcr_alerte: boolean;
  rcr_droit_ouvert: boolean;
  contingent_consomme: number;
  moy_44h_12sem: number;
  alerte_44h_moy: boolean;
}

export interface PayeCollaborateur {
  id: number;
  nom: string;
  initiales: string;
  role: string;
  is_tns: boolean;
  color: string;
  weekly_hours: number;
  jours_travailles: number;
  heures_reelles: number;
  heures_contrat: number | null;
  heures_sup_planning: PayeHeureSup | null;
  detail_semaines: PayeDetailSemaine[] | null;
  heures_dues: number | null;
  heures_nuit_20: number | null;
  heures_nuit_40: number | null;
  heures_dimanche: number | null;
  heures_formation: number;
  cp_poses:          number | null;
  rcr_poses:         number | null;
  conge_exc_poses:   number | null;
  sans_solde_poses:  number | null;
  heures_feries_travaillees: number | null;
  jours_feries_travailles: JourFerieDto[] | null;
  annuel: PayeAnnuel | null;
}

export interface PayeTotauxSalaries {
  jours_travailles: number;
  heures_reelles: number;
  heures_sup_planning_total: number;
  heures_dues: number;
  heures_nuit_20: number;
  heures_nuit_40: number;
  heures_dimanche: number;
  heures_formation: number;
  cp_poses:          number;
  rcr_poses:         number;
  conge_exc_poses:   number;
  sans_solde_poses:  number;
  heures_feries_travaillees: number;
}

export interface PayeSummaryResponse {
  month: string;
  jours_ouvres_mois: number;
  collaborateurs: PayeCollaborateur[];
  totaux_salaries: PayeTotauxSalaries;
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

  getShift(id: number): Observable<Shift> {
    return this.http.get<Shift>(`${this.apiUrl}/shifts/${id}/`);
  }

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

  deleteAbsence(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/absences/${id}/`);
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

  getOpeningHours(week?: string, versionId?: number): Observable<OpeningHours[]> {
    const params: Record<string, string> = {};
    if (week)      params['week']       = week;
    if (versionId) params['version_id'] = String(versionId);
    return this.http.get<OpeningHours[]>(`${this.apiUrl}/opening-hours/`, { params });
  }

  createOpeningHours(dto: { day_of_week: number; start_time: string; end_time: string }, versionId?: number): Observable<OpeningHours> {
    const body = versionId ? { ...dto, version_id: versionId } : dto;
    return this.http.post<OpeningHours>(`${this.apiUrl}/opening-hours/`, body);
  }

  deleteOpeningHours(id: number): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/opening-hours/${id}/`);
  }

  createOpeningHoursVersion(effectiveFrom: string): Observable<OpeningHoursVersion> {
    return this.http.post<OpeningHoursVersion>(`${this.apiUrl}/opening-hours/versions/`, { effective_from: effectiveFrom });
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

  generateTemplate(rotation: number, conversation: ChatMessage[]): Observable<{ task_id: string }> {
    return this.http.post<{ task_id: string }>(`${this.apiUrl}/constraints/generate/`, { rotation, conversation });
  }

  pollGenerateTemplate(taskId: string): Observable<GenerateTemplateResponse & { status: string }> {
    return this.http.get<GenerateTemplateResponse & { status: string }>(
      `${this.apiUrl}/constraints/generate/${taskId}/`
    );
  }

  // ── Drawer shift — actions ────────────────────────────────────────────────

  splitShift(id: number, splitTime: string): Observable<{ shift_1: Shift; shift_2: Shift }> {
    return this.http.post<{ shift_1: Shift; shift_2: Shift }>(
      `${this.apiUrl}/shifts/${id}/split/`, { split_time: splitTime }
    );
  }

  transformShift(id: number, transformType: string): Observable<Shift> {
    return this.http.post<Shift>(
      `${this.apiUrl}/shifts/${id}/transform/`, { transform_type: transformType }
    );
  }

  earlyDeparture(id: number, dto: { actual_end_time: string; note?: string }): Observable<TimeAdjustment> {
    return this.http.post<TimeAdjustment>(`${this.apiUrl}/shifts/${id}/early-departure/`, dto);
  }

  overtimeShift(id: number, dto: { duration_minutes: number; note?: string }): Observable<TimeAdjustment> {
    return this.http.post<TimeAdjustment>(`${this.apiUrl}/shifts/${id}/overtime/`, dto);
  }

  rcrShift(id: number): Observable<AbsenceRequest> {
    return this.http.post<AbsenceRequest>(`${this.apiUrl}/shifts/${id}/rcr/`, {});
  }
}
