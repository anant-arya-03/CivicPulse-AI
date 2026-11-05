// TypeScript mirrors of the backend schemas (backend/app/modules/<module>/schemas.py).
// Keep them in sync when the API changes.

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>;
  };
}

export interface User {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

export interface AuthResponse {
  user: User;
}

// ── Complaints (backend/app/modules/complaints/schemas.py) ───────────────────

export type ComplaintStatus =
  | "DRAFT"
  | "PENDING_REVIEW"
  | "SUBMITTED"
  | "ACKNOWLEDGED"
  | "IN_PROGRESS"
  | "RESOLVED_PENDING_VERIFICATION"
  | "VERIFIED_RESOLVED"
  | "CLOSED"
  | "REOPENED"
  | "CANCELLED";

export type Category =
  | "ROAD_POTHOLE"
  | "BROKEN_STREETLIGHT"
  | "GARBAGE_OVERFLOW"
  | "OPEN_DRAIN"
  | "WATER_LEAKAGE"
  | "WATERLOGGING"
  | "DAMAGED_INFRASTRUCTURE"
  | "OTHER";

export type Severity = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";

export type ComplaintAction =
  | "edit"
  | "add_photo"
  | "cancel"
  | "close"
  | "submit"
  /** Add an "after" photo, confirm or dispute the repair. */
  | "verify"
  /** The problem came back after it was verified or closed. */
  | "reopen";

export interface Evidence {
  id: string;
  evidence_type: "ORIGINAL" | "FOLLOWUP";
  file_type: string;
  file_size_bytes: number;
  width: number | null;
  height: number | null;
  created_at: string;
  url: string;
}

export interface ComplaintLocationFields {
  address_line: string | null;
  locality: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  latitude: number | null;
  longitude: number | null;
}

export interface Complaint extends ComplaintLocationFields {
  id: string;
  public_reference: string;
  title: string | null;
  description: string | null;
  category: Category | null;
  severity: Severity | null;
  status: ComplaintStatus;
  location_confirmed_at: string | null;
  observed_at: string | null;
  /** The formal complaint letter (AI- or template-drafted, then edited by the citizen). */
  draft_subject: string | null;
  draft_body: string | null;
  /** The chosen department (from the directory), or null. */
  authority: Authority | null;
  submitted_at: string | null;
  created_at: string;
  updated_at: string;
  evidence: Evidence[];
  available_actions: ComplaintAction[];
}

/** Fields accepted by POST/PATCH /complaints. Send only what changes. */
export type ComplaintUpdatePayload = Partial<
  Pick<
    Complaint,
    "title" | "description" | "category" | "severity" | "observed_at" | "draft_subject" | "draft_body"
  > &
    ComplaintLocationFields
> & { confirm_location?: boolean };

export interface ComplaintListItem {
  id: string;
  public_reference: string;
  title: string | null;
  category: Category | null;
  severity: Severity | null;
  status: ComplaintStatus;
  locality: string | null;
  city: string | null;
  thumbnail_url: string | null;
  created_at: string;
  updated_at: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export interface ComplaintEvent {
  id: string;
  event_type: string;
  previous_status: ComplaintStatus | null;
  new_status: ComplaintStatus | null;
  description: string;
  actor: "CITIZEN" | "SYSTEM" | "AI" | "AUTHORITY";
  created_at: string;
}

export interface ActivityItem extends ComplaintEvent {
  complaint_id: string;
  complaint_reference: string;
  complaint_title: string | null;
}

export interface DashboardSummary {
  stats: {
    total: number;
    drafts: number;
    active: number;
    pending_responses: number;
    verified_resolutions: number;
  };
  recent_complaints: ComplaintListItem[];
  recent_activity: ActivityItem[];
  needs_attention: AttentionItem[];
}

export type AttentionKind =
  | "VERIFY_FIX"
  | "FOLLOWUP_FAILED"
  | "FOLLOWUP_READY"
  | "REPLY_TO_REVIEW"
  | "INFO_REQUESTED"
  | "ESCALATION";

/** Something the citizen should do on a complaint (backend: monitoring.attention_items). */
export interface AttentionItem {
  complaint_id: string;
  complaint_reference: string;
  complaint_title: string | null;
  kind: AttentionKind;
  message: string;
}

// ── Locations (backend/app/modules/locations/router.py) ──────────────────────

export interface LocationResult {
  label: string;
  address_line: string | null;
  locality: string | null;
  city: string | null;
  state: string | null;
  postal_code: string | null;
  country: string | null;
  latitude: number;
  longitude: number;
}

export type GeocoderProvider = "mock" | "nominatim";

export interface LocationSearchResponse {
  provider: GeocoderProvider;
  results: LocationResult[];
}

export interface ReverseGeocodeResponse {
  provider: GeocoderProvider;
  result: LocationResult | null;
}

// ── AI (backend/app/modules/ai/schemas.py) ───────────────────────────────────

export type Confidence = "HIGH" | "MEDIUM" | "LOW";

/** What the Vision agent suggests for a photo. Suggestions only: the citizen decides. */
export interface VisionAnalysis {
  is_civic_issue: boolean;
  category: Category;
  category_confidence: Confidence;
  suggested_title: string;
  suggested_description: string;
  severity: Severity;
  observations: string[];
  uncertainties: string[];
  warnings: string[];
}

export interface AnalysisRead {
  id: string;
  analysis_type: "VISION" | "COMPLAINT_DRAFT";
  status: "SUCCEEDED" | "FAILED";
  provider: string;
  model: string;
  prompt_version: string;
  /** True when the result came from the demo (mock) provider, not a real AI model. */
  is_mock: boolean;
  evidence_id: string | null;
  result: VisionAnalysis | null;
  error_code: string | null;
  created_at: string;
}

export interface ComplaintDraftResponse {
  draft_subject: string;
  draft_body: string;
  source: "ai" | "template";
  is_mock: boolean;
  analysis_id: string | null;
}

// ── Authorities and submission (backend/app/modules/authorities, communications) ──

export interface Authority {
  id: string;
  name: string;
  jurisdiction: string;
  jurisdiction_level: "WARD" | "CITY" | "DISTRICT" | "STATE" | "NATIONAL";
  city: string | null;
  state: string | null;
  country: string;
  supported_categories: Category[];
  official_email: string | null;
  official_phone: string | null;
  website_url: string | null;
  /** The official page the contact details were taken from (null for demo records). */
  source_url: string | null;
  /** When a person last checked the source (YYYY-MM-DD). */
  verified_at: string | null;
  verification_notes: string | null;
  service_timeline_days: number | null;
  parent_authority_id: string | null;
  /** Fictional record for demonstrations, never a real government contact. */
  is_demo: boolean;
}

export type MatchConfidence = "EXACT" | "PARTIAL" | "NONE";

export interface AuthorityMatchesResponse {
  confidence: MatchConfidence;
  matches: { authority: Authority; score: number; reasons: string[] }[];
  selected_authority_id: string | null;
}

export type DeliveryStatus =
  | "DRAFT"
  | "APPROVED"
  | "SENDING"
  | "SENT"
  | "SIMULATED_SENT"
  | "FAILED"
  | "SUPERSEDED"
  | "CANCELLED"
  | "RECEIVED";

export type ReplyKind =
  | "ACKNOWLEDGMENT"
  | "IN_PROGRESS"
  | "RESOLVED_CLAIM"
  | "REQUEST_FOR_INFO"
  | "REJECTION"
  | "UNRELATED";

export interface Communication {
  id: string;
  direction: "OUTBOUND" | "INBOUND";
  communication_type: "COMPLAINT" | "FOLLOW_UP" | "REPLY";
  channel: string;
  recipient: string | null;
  sender: string | null;
  subject: string;
  body: string;
  attachments: { evidence_id: string; file_type: string }[];
  delivery_status: DeliveryStatus;
  /** True: nothing was sent to a real department. */
  is_simulated: boolean;
  provider: string | null;
  attempt_count: number;
  error_message: string | null;
  sent_at: string | null;
  received_at: string | null;
  created_at: string;
  /** Reminders: 1, 2, ... */
  followup_number: number | null;
  /** Replies: what it means. null = the citizen still has to say. */
  reply_kind: ReplyKind | null;
  reply_kind_source: "AI" | "CITIZEN" | null;
  reply_summary: string | null;
  reference_number: string | null;
}

export interface SubmissionPreview {
  ready: boolean;
  missing: string[];
  authority: Authority | null;
  recipient: string | null;
  from_address: string;
  subject: string | null;
  body: string | null;
  attachments: { evidence_id: string; url: string; file_type: string }[];
  is_simulated: boolean;
  content_sha256: string | null;
  pending_communication: Communication | null;
}

// ── Monitoring & follow-ups (backend/app/modules/monitoring/schemas.py) ──────

export interface MonitoringState {
  /** Waiting for the department: reminders are possible. */
  monitored: boolean;
  response_due_at: string | null;
  deadline_basis: string | null;
  /** True: based on the response time listed for the department. */
  deadline_official: boolean;
  followups_sent: number;
  followups_max: number;
  authority_reference_number: string | null;
  open_followup: Communication | null;
  /** Hash of the open reminder's current text: approving sends it back. */
  open_followup_sha256: string | null;
  replies_to_review: Communication[];
  latest_reply: Communication | null;
  escalation: { recommended_at: string; reason: string; contacts: Authority[] } | null;
}

export interface SimulationInfo {
  enabled: boolean;
  reply_scenarios: { id: string; label: string }[];
}

// ── Resolution verification (backend/app/modules/resolutions/schemas.py) ─────

/** The AI's before/after comparison. Advice only: the citizen decides. */
export interface ResolutionAssessment {
  assessment: "APPEARS_RESOLVED" | "PARTIALLY_RESOLVED" | "NOT_RESOLVED" | "CANNOT_DETERMINE";
  confidence: "HIGH" | "MEDIUM" | "LOW";
  same_location_likely: "YES" | "NO" | "UNSURE";
  visible_changes: string[];
  remaining_problems: string[];
  uncertainties: string[];
  summary: string;
}

export type ResolutionDecision = "CONFIRMED_RESOLVED" | "DISPUTED";

export interface ResolutionReview {
  id: string;
  complaint_id: string;
  followup_evidence: Evidence;
  original_evidence: Evidence | null;
  ai_status: "SUCCEEDED" | "FAILED";
  ai_error_code: string | null;
  is_mock: boolean;
  assessment: ResolutionAssessment | null;
  /** Plain-language warnings (always ends with "The AI can be wrong..."). */
  cautions: string[];
  decision: "PENDING" | ResolutionDecision | "SUPERSEDED";
  citizen_notes: string | null;
  decided_at: string | null;
  created_at: string;
}
