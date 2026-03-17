export interface Procedure {
  id: number;
  title: string;
  reference: string;
  category: ProcedureCategory;
  status: ProcedureStatus;
  content?: string;
  file?: string;
  version: number;
  position: number;
  parent?: number;
  pilot?: { id: number; full_name: string };
  created_by?: { id: number; full_name: string };
  created_at?: string;
  updated_at?: string;
  attachments?: ProcedureAttachment[];
  images?: ProcedureImage[];
  children?: Procedure[];
}

export type ProcedureStatus = 'draft' | 'active' | 'archived';
export type ProcedureCategory = 'dispensation' | 'hygiene' | 'stock' | 'administratif' | 'autre';

export interface ProcedureAttachment {
  id: number;
  filename: string;
  file: string;
  uploaded_at: string;
}

export interface ProcedureImage {
  id: number;
  url: string;
  uploaded_at: string;
}

export interface ReorderPayload {
  id: number;
  parent_id: number | null;
  position: number;
}
