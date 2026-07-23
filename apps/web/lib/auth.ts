import { apiFetch, clearTokens, setTokens } from "./api-client";

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface CurrentUser {
  id: string;
  email: string;
  role: string;
  organization_id: string;
}

export async function register(organizationName: string, email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ organization_name: organizationName, email, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export async function login(email: string, password: string): Promise<void> {
  const tokens = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setTokens(tokens.access_token, tokens.refresh_token);
}

export function logout(): void {
  clearTokens();
}

export async function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me");
}
