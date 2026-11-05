import { api } from "@/lib/api-client";
import type { User } from "@/types/api";

export interface ProfileUpdatePayload {
  name: string;
}

export const accountApi = {
  updateProfile: (payload: ProfileUpdatePayload) => api.patch<User>("/users/me", payload),
};
