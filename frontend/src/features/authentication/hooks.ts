"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { authApi } from "@/features/authentication/api";
import { useHydrationSafeQuery } from "@/lib/hydration";
import type { User } from "@/types/api";

export const authKeys = {
  me: ["auth", "me"] as const,
};

/** The logged-in user. Errors with status 401 when there is no valid session. */
export function useCurrentUser() {
  return useHydrationSafeQuery(
    useQuery<User>({
      queryKey: authKeys.me,
      queryFn: async ({ signal }) => (await authApi.me(signal)).user,
      staleTime: 5 * 60_000,
    }),
  );
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.login,
    onSuccess: ({ user }) => queryClient.setQueryData(authKeys.me, user),
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.register,
    onSuccess: ({ user }) => queryClient.setQueryData(authKeys.me, user),
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: authApi.logout,
    // Forget every cached response so the next user never sees this user's data.
    onSettled: () => queryClient.clear(),
  });
}
