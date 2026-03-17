export interface NonConformity {
  id: number;
  title: string;
  description: string;
  severity: 'minor' | 'major' | 'critical';
  status: 'open' | 'in_progress' | 'closed';
  procedure?: { id: number; title: string };
  reported_by?: { id: number; full_name: string };
  assigned_to?: { id: number; full_name: string };
  due_date?: string;
  closed_at?: string;
  closed_by?: { id: number; full_name: string };
  created_at: string;
  corrective_actions?: CorrectiveAction[];
}

export interface CorrectiveAction {
  id: number;
  description: string;
  responsible?: { id: number; full_name: string };
  due_date?: string;
  completed_at?: string;
  created_at: string;
}
