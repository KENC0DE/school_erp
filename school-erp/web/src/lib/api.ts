import { createApiClient } from "@erp/api-client";

import { clearTokens, getAccessToken } from "./storage";

export const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const api = createApiClient({
  baseUrl: API_URL,
  getToken: getAccessToken,
  onUnauthorized: () => {
    clearTokens();
  },
});

export interface SessionUser {
  id: string;
  email: string | null;
  display_name: string;
  locale: string;
  roles: string[];
  permissions: string[];
  is_controller?: boolean;
  read_only?: boolean;
}

export interface LoginResult {
  tokens: { access_token: string; refresh_token: string; token_type: string; expires_in: number };
  user: SessionUser;
}

export interface NavItem {
  key: string;
  label_key: string;
  path: string;
  icon?: string;
  module: string;
}

export interface Navigation {
  items: NavItem[];
  modules: string[];
  locale: string;
  languages: string[];
}
