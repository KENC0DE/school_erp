export interface ControllerUser {
  id: string;
  email: string | null;
  display_name: string;
  role: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: ControllerUser;
}

export interface School {
  id: string;
  name: string;
  school_code: string;
  api_base_url: string;
  logo_url?: string | null;
  status: string;
  min_app_version?: string;
  plan?: string;
  size_profile?: string;
  modules: string[];
  app_version?: string;
  enrolled: boolean;
  created_at?: string | null;
}

export interface SchoolsResponse {
  items: School[];
  next_cursor: string | null;
}

export interface SupportSession {
  token: string;
  expires_at: string;
  read_only: boolean;
  reason: string;
  instance_id: string;
}

export interface VaultItem {
  id: string;
  school_id: string;
  school_name: string | null;
  seq: number;
  action: string | null;
  module: string | null;
  actor_type: string | null;
  actor_id: string | null;
  via: string | null;
  entity_type: string | null;
  entity_id: string | null;
  ts: string | number | null;
  chain_ok: boolean;
}

export interface VaultResponse {
  items: VaultItem[];
  next_cursor: string | null;
}

export interface VaultStatus {
  school_id: string;
  last_seq: number;
  chain_head: string | null;
  entries: number;
  broken_entries: number;
  ok: boolean;
}

/**
 * Mirrors `LICENSABLE_MODULES` in `owner/controller-api/controller_api/licenses.py`.
 * It is duplicated (not imported) because owner/controller-web may only use
 * shared/ packages and HTTP APIs, never controller-api source.
 */
export const LICENSABLE_MODULES = [
  "academics",
  "students",
  "admissions",
  "staff",
  "attendance",
  "assessment",
  "timetable",
  "fees",
  "documents",
  "communication",
  "portals",
  "ai",
  "automation",
  "sample",
] as const;
