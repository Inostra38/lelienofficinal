export interface ProcedureGroup {
  id: number;
  name: string;
  description?: string;
  color: string;
  procedure_count: number;
  created_by?: { id: number; full_name: string };
  created_at?: string;
  updated_at?: string;
}

export interface ProcedureCategory {
  id: number;
  name: string;
  color: string;
}

export interface ProcedureVersion {
  id: number;
  version_number: number;
  content: string;
  change_summary: string;
  created_by: { id: number; full_name: string } | null;
  created_at: string;
}

export interface Procedure {
  id: number;
  title: string;
  reference: string | null;
  categories: ProcedureCategory[];
  status: ProcedureStatus;
  content?: string;
  file?: string;
  version: number;
  position: number;
  parent_id?: number | null;
  last_published_version?: number | null;
  next_review_date?: string | null;
  is_unread?: boolean;
  group?: number | null;
  pilots?: { id: number; full_name: string; initials: string; color: string }[];
  created_by?: { id: number; full_name: string; color: string };
  archived_by?: { id: number; full_name: string; color: string } | null;
  created_at?: string;
  updated_at?: string;
  archived_at?: string | null;
  group_name?: string;
  attachments?: ProcedureAttachment[];
  images?: ProcedureImage[];
  history?: ProcedureVersion[];
}

export type ProcedureStatus = 'draft' | 'active' | 'archived';

export interface ProcedureAttachment {
  id: number;
  filename: string;
  original_name: string;
  file: string;
  file_type: 'image' | 'document';
  uploaded_at: string;
}

export interface ProcedureImage {
  id: number;
  url: string;
  uploaded_at: string;
}

export interface ReorderPayload {
  id: number;
  position: number;
  group_id?: number | null;
  parent_id?: number | null;
}
