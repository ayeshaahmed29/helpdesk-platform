import { apiFetch } from "./client";

export type UserRole = "customer" | "agent" | "admin" | "owner";

export interface CurrentUser {
  id: number;
  email: string;
  full_name: string;
  role: UserRole;
  organization_id: number;
}

export interface MessageResponse {
  message: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface SignupData {
  organization_name: string;
  full_name: string;
  email: string;
  password: string;
}

export function getCurrentUser(): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/me");
}

export function loginRequest(email: string, password: string): Promise<TokenResponse> {
  return apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function signupRequest(data: SignupData): Promise<CurrentUser> {
  return apiFetch<CurrentUser>("/auth/signup", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function forgotPassword(email: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, newPassword: string): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
}