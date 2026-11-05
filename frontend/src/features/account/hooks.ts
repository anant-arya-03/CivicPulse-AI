"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { accountApi } from "@/features/account/api";
import { authKeys } from "@/features/authentication/hooks";

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: accountApi.updateProfile,
    // The current user is cached under authKeys.me; refresh it everywhere at once.
    onSuccess: (user) => queryClient.setQueryData(authKeys.me, user),
  });
}
