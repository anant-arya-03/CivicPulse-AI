import { api } from "@/lib/api-client";
import type { AuthResponse } from "@/types/api";

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload extends LoginPayload {
  name: string;
}

export const authApi = {
  me: (signal?: AbortSignal) => api.get<AuthResponse>("/auth/me", signal),
  login: (payload: LoginPayload) => api.post<AuthResponse>("/auth/login", payload),
  register: (payload: RegisterPayload) => api.post<AuthResponse>("/auth/register", payload),
  logout: () => api.post<void>("/auth/logout"),
};
