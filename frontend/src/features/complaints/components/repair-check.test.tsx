import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RepairCheck } from "@/features/complaints/components/repair-check";
import type { Complaint, Evidence, ResolutionReview } from "@/types/api";

function photo(id: string, type: Evidence["evidence_type"]): Evidence {
  return {
    id,
    evidence_type: type,
    file_type: "image/jpeg",
    file_size_bytes: 1000,
    width: 800,
    height: 600,
    created_at: "2026-11-20T10:00:00Z",
    url: `/api/v1/evidence/${id}/file`,
  };
}

const claimed = {
  id: "c1",
  public_reference: "CP-2026-000001",
  status: "RESOLVED_PENDING_VERIFICATION",
  submitted_at: "2026-11-04T10:00:00Z",
  available_actions: ["verify"],
} as Complaint;

function review(overrides: Partial<ResolutionReview> = {}): ResolutionReview {
  return {
    id: "r1",
    complaint_id: "c1",
    followup_evidence: photo("after1", "FOLLOWUP"),
    original_evidence: photo("before", "ORIGINAL"),
    ai_status: "SUCCEEDED",
    ai_error_code: null,
    is_mock: true,
    assessment: {
      assessment: "APPEARS_RESOLVED",
      confidence: "MEDIUM",
      same_location_likely: "YES",
      visible_changes: ["The hole appears to have been filled"],
      remaining_problems: [],
      uncertainties: ["The quality of the repair cannot be judged"],
      summary: "The problem appears to have been repaired.",
    },
    cautions: ["The AI can be wrong. Only your own check decides."],
    decision: "PENDING",
    citizen_notes: null,
    decided_at: null,
    created_at: "2026-11-20T10:00:00Z",
    ...overrides,
  };
}

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const fetchMock = vi.fn<typeof fetch>();

function routeFetch(reviews: ResolutionReview[], routes: Record<string, () => Promise<Response>> = {}) {
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "GET" && url.endsWith("/resolution-reviews")) return json(200, reviews);
    const key = Object.keys(routes).find((k) => {
      const [m, end] = k.split(" ");
      return m === method && url.endsWith(end);
    });
    if (key) return routes[key]();
    return json(404, { error: { code: "NOT_FOUND", message: "Unexpected request", details: {} } });
  });
}

const calls = (method: string, end: string) =>
  fetchMock.mock.calls.filter(([input, init]) => (init?.method ?? "GET") === method && String(input).endsWith(end));

function renderCheck(complaint: Complaint = claimed) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <RepairCheck complaint={complaint} />
    </QueryClientProvider>,
  );
}

describe("RepairCheck", () => {
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("shows nothing before the complaint is sent", () => {
    renderCheck({ ...claimed, status: "DRAFT", submitted_at: null, available_actions: ["edit"] });
    expect(screen.queryByText("Check the repair")).not.toBeInTheDocument();
  });

  it("asks for a new photo when the department claims a repair", async () => {
    routeFetch([]);
    renderCheck();
    expect(await screen.findByText(/Take a new photo of the same place/)).toBeInTheDocument();
    expect(await screen.findByText(/A new photo of the same place, from a similar angle/)).toBeInTheDocument();
  });

  it("rejects an unsupported photo before uploading it", async () => {
    const user = userEvent.setup({ applyAccept: false });
    routeFetch([]);
    renderCheck();
    await screen.findByText(/A new photo of the same place, from a similar angle/);
    const input = document.querySelector<HTMLInputElement>('input[type="file"]');
    await waitFor(() => expect(input).toBeEnabled());
    await user.upload(input!, new File(["x"], "IMG_1.HEIC", { type: "image/heic" }));
    expect(await screen.findByText(/HEIC photos aren't supported/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledTimes(1); // only the GET of earlier checks
  });

  it("shows the AI's opinion as advice next to the two photos", async () => {
    routeFetch([review()]);
    renderCheck();
    const region = await screen.findByRole("region", { name: "Before and after" });
    expect(within(region).getByRole("img", { name: "Before (your complaint)" })).toBeInTheDocument();
    expect(within(region).getByRole("img", { name: /^After/ })).toBeInTheDocument();
    expect(within(region).getByText("The AI thinks:")).toBeInTheDocument();
    expect(within(region).getByText("Appears repaired")).toBeInTheDocument();
    expect(within(region).getByText("Demo AI")).toBeInTheDocument();
    expect(within(region).getByText(/Only your own check decides/)).toBeInTheDocument();
  });

  it("confirming needs a choice and 'I checked myself', and is sent once", async () => {
    const user = userEvent.setup();
    let finish: (r: Response) => void = () => {};
    routeFetch([review()], {
      "POST /resolution-reviews/r1/decision": () => new Promise((resolve) => (finish = resolve)),
    });
    renderCheck();
    const save = await screen.findByRole("button", { name: "Save my decision" });
    expect(save).toBeDisabled();
    await user.click(screen.getByLabelText(/Yes, it's fixed/));
    expect(save).toBeDisabled(); // still needs the confirmation
    await user.click(screen.getByLabelText(/I checked the place myself/));
    await user.type(screen.getByLabelText(/What did you find/), "Smooth road now");
    await user.click(save);
    await user.click(save); // a double click must not decide twice
    await waitFor(() => expect(calls("POST", "/decision")).toHaveLength(1));
    expect(JSON.parse(String(calls("POST", "/decision")[0][1]?.body))).toEqual({
      decision: "CONFIRMED_RESOLVED",
      notes: "Smooth road now",
      checked_myself: true,
    });
    finish(json(200, review({ decision: "CONFIRMED_RESOLVED" })));
  });

  it("'not fixed' is only possible after the department reported a repair", async () => {
    routeFetch([review()]);
    renderCheck({ ...claimed, status: "IN_PROGRESS" });
    const notFixed = await screen.findByLabelText(/No, it's not fixed/);
    expect(notFixed).toBeDisabled();
    expect(screen.getByText(/Available once the department reports a repair/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Yes, it's fixed/)).toBeEnabled();
  });

  it("without the AI, the citizen compares the photos and can retry the AI", async () => {
    const user = userEvent.setup();
    routeFetch(
      [
        review({
          ai_status: "FAILED",
          ai_error_code: "PROVIDER_ERROR",
          assessment: null,
          is_mock: false,
          cautions: ["The AI comparison isn't available. Please compare the two photos yourself."],
        }),
      ],
      { "POST /complaints/c1/resolution-reviews": async () => json(201, review()) },
    );
    renderCheck();
    expect(await screen.findByText("No AI comparison")).toBeInTheDocument();
    expect(screen.getByText(/compare the two photos yourself/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save my decision" })).toBeInTheDocument(); // manual path
    await user.click(screen.getByRole("button", { name: /Try the AI again/ }));
    await waitFor(() => expect(calls("POST", "/resolution-reviews")).toHaveLength(1));
    expect(JSON.parse(String(calls("POST", "/resolution-reviews")[0][1]?.body))).toEqual({ evidence_id: "after1" });
  });

  it("uncertainty is spelled out", async () => {
    routeFetch([
      review({
        assessment: { ...review().assessment!, assessment: "CANNOT_DETERMINE", confidence: "LOW", same_location_likely: "NO" },
        cautions: [
          "The AI thinks the photos may show different places. Check that the new photo shows the same spot.",
          "The AI is not confident about this comparison.",
          "The AI can be wrong. Only your own check decides.",
        ],
      }),
    ]);
    renderCheck();
    expect(await screen.findByText("Can't tell from these photos")).toBeInTheDocument();
    expect(screen.getByText(/may show different places/)).toBeInTheDocument();
    expect(screen.getByText("(low confidence)")).toBeInTheDocument();
  });

  it("keeps the history of earlier checks", async () => {
    routeFetch([
      review({ id: "r0", decision: "SUPERSEDED" }),
      review({ id: "r1", decision: "DISPUTED", citizen_notes: "Still a hole.", decided_at: "2026-11-21T10:00:00Z" }),
    ]);
    renderCheck({ ...claimed, status: "VERIFIED_RESOLVED", available_actions: ["reopen", "close"] });
    const history = await screen.findByRole("region", { name: "Earlier checks" });
    expect(within(history).getByText("You said it's not fixed")).toBeInTheDocument();
    expect(within(history).getByText("Replaced by a newer photo")).toBeInTheDocument();
    expect(within(history).getByText("“Still a hole.”")).toBeInTheDocument();
    expect(screen.queryByText(/A new photo of the same place/)).not.toBeInTheDocument(); // nothing to check now
  });
});
