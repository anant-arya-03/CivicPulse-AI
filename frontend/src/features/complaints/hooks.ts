"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  aiApi,
  authoritiesApi,
  complaintsApi,
  locationsApi,
  monitoringApi,
  resolutionApi,
  simulationApi,
  submissionApi,
  type ComplaintListParams,
} from "@/features/complaints/api";
import { useHydrationSafeQuery } from "@/lib/hydration";
import type {
  Category,
  Complaint,
  ComplaintUpdatePayload,
  ReplyKind,
  ResolutionDecision,
} from "@/types/api";

export const complaintKeys = {
  all: ["complaints"] as const,
  list: (params: ComplaintListParams) => ["complaints", "list", params] as const,
  detail: (id: string) => ["complaints", "detail", id] as const,
  timeline: (id: string) => ["complaints", "timeline", id] as const,
  dashboard: ["dashboard", "summary"] as const,
  analysis: (id: string) => ["complaints", "analysis", id] as const,
  matches: (id: string) => ["complaints", "authority-matches", id] as const,
  preview: (id: string) => ["complaints", "submission-preview", id] as const,
  history: (id: string) => ["complaints", "communications", id] as const,
  monitoring: (id: string) => ["complaints", "monitoring", id] as const,
  simulation: ["simulation"] as const,
  resolutions: (id: string) => ["complaints", "resolution-reviews", id] as const,
};

// ── Reading ─────────────────────────────────────────────────────────────────

export function useComplaintList(params: ComplaintListParams) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.list(params),
      queryFn: ({ signal }) => complaintsApi.list(params, signal),
      placeholderData: keepPreviousData, // keep showing the old page while the next one loads
    }),
  );
}

export function useComplaint(id: string | null) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.detail(id ?? ""),
      queryFn: ({ signal }) => complaintsApi.get(id!, signal),
      enabled: Boolean(id),
    }),
  );
}

export function useComplaintTimeline(id: string) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.timeline(id),
      queryFn: ({ signal }) => complaintsApi.timeline(id, signal),
    }),
  );
}

export function useDashboardSummary() {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.dashboard,
      queryFn: ({ signal }) => complaintsApi.dashboard(signal),
    }),
  );
}

/** Address search. Runs only when `query` is set, i.e. when the user presses Search. */
export function useLocationSearch(query: string) {
  return useQuery({
    queryKey: ["locations", "search", query],
    queryFn: ({ signal }) => locationsApi.search(query, signal),
    enabled: query.length >= 3,
    staleTime: 10 * 60_000,
  });
}

// ── Writing ─────────────────────────────────────────────────────────────────

/** After any change, store the fresh complaint and refresh lists, timeline, and dashboard. */
function useComplaintChanged() {
  const queryClient = useQueryClient();
  return (complaint: Complaint) => {
    queryClient.setQueryData(complaintKeys.detail(complaint.id), complaint);
    void queryClient.invalidateQueries({ queryKey: complaintKeys.all });
    void queryClient.invalidateQueries({ queryKey: complaintKeys.dashboard });
  };
}

export function useCreateComplaint() {
  const onChanged = useComplaintChanged();
  return useMutation({
    mutationFn: (payload: ComplaintUpdatePayload = {}) => complaintsApi.create(payload),
    onSuccess: onChanged,
  });
}

export function useUpdateComplaint(id: string) {
  const onChanged = useComplaintChanged();
  return useMutation({
    mutationFn: (payload: ComplaintUpdatePayload) => complaintsApi.update(id, payload),
    onSuccess: onChanged,
  });
}

export function useCancelComplaint(id: string) {
  const onChanged = useComplaintChanged();
  return useMutation({ mutationFn: () => complaintsApi.cancel(id), onSuccess: onChanged });
}

export function useCloseComplaint(id: string) {
  const onChanged = useComplaintChanged();
  return useMutation({ mutationFn: () => complaintsApi.close(id), onSuccess: onChanged });
}

/** Photo upload/removal changes the complaint, so reload it afterwards. */
function usePhotoChanged() {
  const queryClient = useQueryClient();
  return (complaintId: string) => {
    void queryClient.invalidateQueries({ queryKey: complaintKeys.all });
    void queryClient.invalidateQueries({ queryKey: complaintKeys.dashboard });
    return queryClient.fetchQuery({
      queryKey: complaintKeys.detail(complaintId),
      queryFn: () => complaintsApi.get(complaintId),
      staleTime: 0,
    });
  };
}

export function useUploadPhoto() {
  const onPhotoChanged = usePhotoChanged();
  return useMutation({
    mutationFn: (vars: { complaintId: string; file: File; onProgress?: (p: number) => void }) =>
      complaintsApi.uploadPhoto(vars.complaintId, vars.file, vars.onProgress),
    onSuccess: (_evidence, vars) => onPhotoChanged(vars.complaintId),
  });
}

export function useDeletePhoto() {
  const onPhotoChanged = usePhotoChanged();
  return useMutation({
    mutationFn: (vars: { complaintId: string; evidenceId: string }) =>
      complaintsApi.deletePhoto(vars.evidenceId),
    onSuccess: (_result, vars) => onPhotoChanged(vars.complaintId),
  });
}

// ── AI ──────────────────────────────────────────────────────────────────────

export function useLatestAnalysis(complaintId: string) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.analysis(complaintId),
      queryFn: ({ signal }) => aiApi.latest(complaintId, signal),
    }),
  );
}

export function useAnalyzePhoto(complaintId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (evidenceId?: string) => aiApi.analyze(complaintId, evidenceId),
    onSuccess: (analysis) => queryClient.setQueryData(complaintKeys.analysis(complaintId), analysis),
    // Success or failure, the timeline gained an event.
    onSettled: () => queryClient.invalidateQueries({ queryKey: complaintKeys.timeline(complaintId) }),
  });
}

export function useDraftLetter(complaintId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { mode: "ai" | "template"; replace_existing?: boolean }) =>
      aiApi.draftLetter(complaintId, body),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: complaintKeys.detail(complaintId) });
      void queryClient.invalidateQueries({ queryKey: complaintKeys.timeline(complaintId) });
    },
  });
}

// ── Departments and submission ─────────────────────────────────────────────

export function useAuthorityMatches(complaintId: string) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.matches(complaintId),
      queryFn: ({ signal }) => authoritiesApi.matches(complaintId, signal),
    }),
  );
}

export function useAuthoritySearch(params: { q?: string; category?: Category }, enabled: boolean) {
  return useQuery({
    queryKey: ["authorities", params],
    queryFn: ({ signal }) => authoritiesApi.search(params, signal),
    enabled,
  });
}

export function useSelectAuthority(complaintId: string) {
  const onChanged = useComplaintChanged();
  return useMutation({
    mutationFn: (authorityId: string) => authoritiesApi.select(complaintId, authorityId),
    onSuccess: onChanged,
  });
}

export function useSubmissionPreview(complaintId: string) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.preview(complaintId),
      queryFn: ({ signal }) => submissionApi.preview(complaintId, signal),
      staleTime: 0, // always show exactly what would be sent now
    }),
  );
}

export function useCommunications(complaintId: string) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.history(complaintId),
      queryFn: ({ signal }) => submissionApi.history(complaintId, signal),
    }),
  );
}

/** Approve (unless already approved) and send. Throws ApiError on failure. */
export function useApproveAndSend(complaintId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (vars: { contentSha256: string; pendingId?: string }) => {
      const messageId =
        vars.pendingId ?? (await submissionApi.approve(complaintId, vars.contentSha256)).id;
      return submissionApi.send(messageId);
    },
    onSettled: () => {
      // Sent, failed, or only approved: refresh everything that shows it.
      void queryClient.invalidateQueries({ queryKey: complaintKeys.all });
      void queryClient.invalidateQueries({ queryKey: complaintKeys.dashboard });
    },
  });
}

// ── Response tracking & reminders ───────────────────────────────────────────

export function useMonitoring(complaintId: string, enabled = true) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.monitoring(complaintId),
      queryFn: ({ signal }) => monitoringApi.get(complaintId, signal),
      enabled,
    }),
  );
}

/** After any change to a complaint's messages: refresh everything that shows them. */
function useRefreshComplaints() {
  const queryClient = useQueryClient();
  return () => {
    void queryClient.invalidateQueries({ queryKey: complaintKeys.all });
    void queryClient.invalidateQueries({ queryKey: complaintKeys.dashboard });
  };
}

export function useUpdateFollowup() {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (vars: { id: string; subject: string; body: string }) =>
      monitoringApi.updateFollowup(vars.id, { subject: vars.subject, body: vars.body }),
    onSettled: refresh,
  });
}

/** Approve the reminder (unless already approved) and send it. Throws ApiError on failure. */
export function useApproveAndSendFollowup() {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: async (vars: { id: string; contentSha256: string; alreadyApproved: boolean }) => {
      if (!vars.alreadyApproved) await monitoringApi.approveFollowup(vars.id, vars.contentSha256);
      return submissionApi.send(vars.id);
    },
    onSettled: refresh,
  });
}

export function useDismissFollowup() {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (id: string) => monitoringApi.dismissFollowup(id),
    onSettled: refresh,
  });
}

export function useSetReplyKind() {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (vars: { id: string; kind: ReplyKind }) =>
      monitoringApi.setReplyKind(vars.id, vars.kind),
    onSettled: refresh,
  });
}

// ── Demo tools (only when the backend has ENABLE_SIMULATION=true) ───────────

export function useSimulationInfo() {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.simulation,
      queryFn: ({ signal }) => simulationApi.info(signal),
      staleTime: Infinity,
    }),
  );
}

export function useSimulateReply(complaintId: string) {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (scenario: string) => simulationApi.reply(complaintId, scenario),
    onSettled: refresh,
  });
}

export function useAdvanceTime(complaintId: string) {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: () => simulationApi.advance(complaintId),
    onSettled: refresh,
  });
}

// ── Checking a repair ───────────────────────────────────────────────────────

export function useResolutionReviews(complaintId: string, enabled = true) {
  return useHydrationSafeQuery(
    useQuery({
      queryKey: complaintKeys.resolutions(complaintId),
      queryFn: ({ signal }) => resolutionApi.history(complaintId, signal),
      enabled,
    }),
  );
}

/** Upload the "after" photo, then ask the AI to compare it. The comparison never fails the
 * whole step: if the AI is unavailable the check comes back with ai_status FAILED. */
export function useCheckRepair(complaintId: string) {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: async (vars: { file: File; onProgress?: (percent: number) => void }) => {
      const photo = await resolutionApi.uploadAfterPhoto(complaintId, vars.file, vars.onProgress);
      return resolutionApi.compare(complaintId, photo.id);
    },
    onSettled: refresh,
  });
}

export function useRetryComparison(complaintId: string) {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (evidenceId: string) => resolutionApi.compare(complaintId, evidenceId),
    onSettled: refresh,
  });
}

export function useDecideRepair() {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (vars: { reviewId: string; decision: ResolutionDecision; notes: string }) =>
      resolutionApi.decide(vars.reviewId, vars.decision, vars.notes),
    onSettled: refresh,
  });
}

export function useReopenComplaint(complaintId: string) {
  const refresh = useRefreshComplaints();
  return useMutation({
    mutationFn: (notes: string) => resolutionApi.reopen(complaintId, notes),
    onSettled: refresh,
  });
}
