import { api, uploadFile } from "@/lib/api-client";
import type {
  AnalysisRead,
  Authority,
  AuthorityMatchesResponse,
  Category,
  Communication,
  Complaint,
  ComplaintDraftResponse,
  ComplaintEvent,
  ComplaintListItem,
  ComplaintStatus,
  ComplaintUpdatePayload,
  DashboardSummary,
  Evidence,
  LocationSearchResponse,
  MonitoringState,
  Page,
  ReplyKind,
  ResolutionDecision,
  ResolutionReview,
  ReverseGeocodeResponse,
  SimulationInfo,
  SubmissionPreview,
} from "@/types/api";

export type ComplaintSort = "-created_at" | "created_at" | "-updated_at";

export interface ComplaintListParams {
  search?: string;
  category?: Category;
  status?: ComplaintStatus;
  sort?: ComplaintSort;
  page?: number;
  pageSize?: number;
}

function toQueryString(params: ComplaintListParams): string {
  const query = new URLSearchParams();
  if (params.search) query.set("search", params.search);
  if (params.category) query.set("category", params.category);
  if (params.status) query.set("status", params.status);
  if (params.sort) query.set("sort", params.sort);
  if (params.page) query.set("page", String(params.page));
  if (params.pageSize) query.set("page_size", String(params.pageSize));
  const text = query.toString();
  return text ? `?${text}` : "";
}

export const complaintsApi = {
  list: (params: ComplaintListParams, signal?: AbortSignal) =>
    api.get<Page<ComplaintListItem>>(`/complaints${toQueryString(params)}`, signal),
  get: (id: string, signal?: AbortSignal) => api.get<Complaint>(`/complaints/${id}`, signal),
  timeline: (id: string, signal?: AbortSignal) =>
    api.get<ComplaintEvent[]>(`/complaints/${id}/timeline`, signal),
  create: (payload: ComplaintUpdatePayload = {}) => api.post<Complaint>("/complaints", payload),
  update: (id: string, payload: ComplaintUpdatePayload) =>
    api.patch<Complaint>(`/complaints/${id}`, payload),
  cancel: (id: string) => api.post<Complaint>(`/complaints/${id}/cancel`),
  close: (id: string) => api.post<Complaint>(`/complaints/${id}/close`),
  uploadPhoto: (id: string, file: File, onProgress?: (percent: number) => void) =>
    uploadFile<Evidence>(`/complaints/${id}/evidence`, file, { onProgress }),
  deletePhoto: (evidenceId: string) => api.delete<void>(`/evidence/${evidenceId}`),
  dashboard: (signal?: AbortSignal) => api.get<DashboardSummary>("/dashboard/summary", signal),
};

export const aiApi = {
  /** Ask the AI to analyse a photo (defaults to the complaint's first photo). */
  analyze: (complaintId: string, evidenceId?: string) =>
    api.post<AnalysisRead>(`/complaints/${complaintId}/analysis`, { evidence_id: evidenceId ?? null }),
  /** The latest successful analysis, or null. */
  latest: (complaintId: string, signal?: AbortSignal) =>
    api.get<AnalysisRead | null>(`/complaints/${complaintId}/analysis`, signal),
  /** mode "template" writes the letter without AI (the manual fallback). */
  draftLetter: (complaintId: string, body: { mode: "ai" | "template"; replace_existing?: boolean }) =>
    api.post<ComplaintDraftResponse>(`/complaints/${complaintId}/complaint-draft`, body),
};

export const locationsApi = {
  search: (query: string, signal?: AbortSignal) =>
    api.get<LocationSearchResponse>(`/locations/search?q=${encodeURIComponent(query)}`, signal),
  reverse: (latitude: number, longitude: number) =>
    api.get<ReverseGeocodeResponse>(`/locations/reverse?lat=${latitude}&lon=${longitude}`),
};

export const authoritiesApi = {
  search: (params: { q?: string; category?: Category }, signal?: AbortSignal) => {
    const query = new URLSearchParams();
    if (params.q) query.set("q", params.q);
    if (params.category) query.set("category", params.category);
    return api.get<Authority[]>(`/authorities?${query.toString()}`, signal);
  },
  matches: (complaintId: string, signal?: AbortSignal) =>
    api.get<AuthorityMatchesResponse>(`/complaints/${complaintId}/authority-matches`, signal),
  select: (complaintId: string, authorityId: string) =>
    api.put<Complaint>(`/complaints/${complaintId}/authority`, { authority_id: authorityId }),
};

export const submissionApi = {
  preview: (complaintId: string, signal?: AbortSignal) =>
    api.get<SubmissionPreview>(`/complaints/${complaintId}/submission-preview`, signal),
  /** `contentSha256` must be the hash from the preview the citizen looked at. */
  approve: (complaintId: string, contentSha256: string) =>
    api.post<Communication>(`/complaints/${complaintId}/approve`, {
      confirm: true,
      content_sha256: contentSha256,
    }),
  send: (communicationId: string) =>
    api.post<Communication>(`/communications/${communicationId}/send`),
  history: (complaintId: string, signal?: AbortSignal) =>
    api.get<Communication[]>(`/complaints/${complaintId}/communications`, signal),
};

/** Response tracking: replies, reminders (drafted by the backend, approved by the citizen). */
export const monitoringApi = {
  get: (complaintId: string, signal?: AbortSignal) =>
    api.get<MonitoringState>(`/complaints/${complaintId}/monitoring`, signal),
  updateFollowup: (communicationId: string, changes: { subject?: string; body?: string }) =>
    api.patch<Communication>(`/communications/${communicationId}`, changes),
  /** `contentSha256` must be the hash of the reminder text the citizen looked at. */
  approveFollowup: (communicationId: string, contentSha256: string) =>
    api.post<Communication>(`/communications/${communicationId}/approve`, {
      confirm: true,
      content_sha256: contentSha256,
    }),
  dismissFollowup: (communicationId: string) =>
    api.post<Communication>(`/communications/${communicationId}/dismiss`),
  setReplyKind: (communicationId: string, kind: ReplyKind) =>
    api.put<Communication>(`/communications/${communicationId}/reply-kind`, { kind }),
};

/** Development/demo only (ENABLE_SIMULATION=true on the backend). */
export const simulationApi = {
  info: (signal?: AbortSignal) => api.get<SimulationInfo>("/simulation", signal),
  reply: (complaintId: string, scenario: string) =>
    api.post<Communication>(`/complaints/${complaintId}/simulation/reply`, { scenario }),
  advance: (complaintId: string) =>
    api.post<{ ran: { outcome: string | null }[] }>(`/complaints/${complaintId}/simulation/advance`),
};

/** Checking a repair: an "after" photo, the AI's comparison (advice), the citizen's decision. */
export const resolutionApi = {
  uploadAfterPhoto: (complaintId: string, file: File, onProgress?: (percent: number) => void) =>
    uploadFile<Evidence>(`/complaints/${complaintId}/followup-evidence`, file, { onProgress }),
  /** Compare the photo with the original. Asking again retries a failed AI comparison. */
  compare: (complaintId: string, evidenceId: string) =>
    api.post<ResolutionReview>(`/complaints/${complaintId}/resolution-reviews`, {
      evidence_id: evidenceId,
    }),
  history: (complaintId: string, signal?: AbortSignal) =>
    api.get<ResolutionReview[]>(`/complaints/${complaintId}/resolution-reviews`, signal),
  decide: (reviewId: string, decision: ResolutionDecision, notes: string) =>
    api.post<ResolutionReview>(`/resolution-reviews/${reviewId}/decision`, {
      decision,
      notes: notes.trim() || null,
      checked_myself: true,
    }),
  reopen: (complaintId: string, notes: string) =>
    api.post<Complaint>(`/complaints/${complaintId}/reopen`, {
      notes: notes.trim() || null,
      checked_myself: true,
    }),
};
