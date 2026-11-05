import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { DetailsStep } from "@/features/complaints/report-wizard/details-step";
import type { AnalysisRead, Complaint } from "@/types/api";

const PHOTO_ID = "photo-1";

function makeComplaint(overrides: Partial<Complaint> = {}): Complaint {
  return {
    id: "c1",
    public_reference: "CP-2026-000001",
    title: null,
    description: null,
    category: null,
    severity: null,
    status: "DRAFT",
    address_line: null,
    locality: null,
    city: null,
    state: null,
    postal_code: null,
    country: null,
    latitude: null,
    longitude: null,
    location_confirmed_at: null,
    observed_at: null,
    draft_subject: null,
    draft_body: null,
    authority: null,
    submitted_at: null,
    created_at: "2026-11-03T10:00:00Z",
    updated_at: "2026-11-03T10:00:00Z",
    evidence: [
      {
        id: PHOTO_ID,
        evidence_type: "ORIGINAL",
        file_type: "image/jpeg",
        file_size_bytes: 1000,
        width: 800,
        height: 600,
        created_at: "2026-11-03T10:00:00Z",
        url: "/api/v1/evidence/photo-1/file",
      },
    ],
    available_actions: ["edit", "cancel"],
    ...overrides,
  };
}

const analysis: AnalysisRead = {
  id: "a1",
  analysis_type: "VISION",
  status: "SUCCEEDED",
  provider: "mock",
  model: "mock-v1",
  prompt_version: "vision.v1",
  is_mock: true,
  evidence_id: PHOTO_ID,
  error_code: null,
  created_at: "2026-11-03T10:01:00Z",
  result: {
    is_civic_issue: true,
    category: "ROAD_POTHOLE",
    category_confidence: "HIGH",
    suggested_title: "Pothole on the road surface",
    suggested_description: "A pothole is visible on the road surface.",
    severity: "MEDIUM",
    observations: ["A roughly oval hole in the asphalt"],
    uncertainties: ["The depth cannot be judged from the photo"],
    warnings: [],
  },
};

function json(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const fetchMock = vi.fn<typeof fetch>();

/** GET /analysis -> nothing yet. POST /analysis -> whatever the test provides. */
function routeFetch(analyzeResponse: () => Promise<Response>) {
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/analysis") && init?.method === "POST") return analyzeResponse();
    if (url.endsWith("/analysis")) return json(200, null);
    return json(404, { error: { code: "NOT_FOUND", message: "Unexpected request", details: {} } });
  });
}

/** Wait until the component has actually asked the AI to analyse the photo. */
async function waitForAnalysisRequest() {
  await waitFor(() =>
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/analysis"),
      expect.objectContaining({ method: "POST" }),
    ),
  );
}

function renderStep(complaint: Complaint) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <DetailsStep complaint={complaint} onBack={() => {}} onContinue={() => {}} />
    </QueryClientProvider>,
  );
}

describe("DetailsStep with AI analysis", () => {
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));
  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("shows the analysing state, then fills empty fields and labels the demo AI", async () => {
    let finish: (r: Response) => void = () => {};
    routeFetch(() => new Promise((resolve) => (finish = resolve)));
    renderStep(makeComplaint());

    expect(await screen.findByText(/Looking at your photo/)).toBeInTheDocument();
    await waitForAnalysisRequest();
    finish(json(201, analysis));

    expect(await screen.findByText("Demo AI")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Pothole on the road surface");
    expect(screen.getByLabelText("Description")).toHaveValue("A pothole is visible on the road surface.");
    expect(screen.getAllByText("Suggested by AI. Please check it.").length).toBeGreaterThan(0);
    expect(screen.getByText("A roughly oval hole in the asphalt")).toBeInTheDocument();
  });

  it("never overwrites a title the citizen already has, but offers the suggestion", async () => {
    routeFetch(async () => json(201, analysis));
    renderStep(makeComplaint({ title: "Huge hole outside my gate" }));

    expect(await screen.findByText("AI suggests:")).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Huge hole outside my gate");

    await userEvent.click(screen.getByRole("button", { name: "Use suggestion" }));
    expect(screen.getByLabelText("Title")).toHaveValue("Pothole on the road surface");
  });

  it("keeps text the citizen types while the AI is still working", async () => {
    let finish: (r: Response) => void = () => {};
    routeFetch(() => new Promise((resolve) => (finish = resolve)));
    renderStep(makeComplaint());

    await screen.findByText(/Looking at your photo/);
    await waitForAnalysisRequest();
    await userEvent.type(screen.getByLabelText("Description"), "Water is pouring out of it.");
    finish(json(201, analysis));

    await screen.findByText("Demo AI");
    expect(screen.getByLabelText("Description")).toHaveValue("Water is pouring out of it.");
    expect(screen.getByLabelText("Title")).toHaveValue("Pothole on the road surface"); // was empty
  });

  it("offers the manual path when the AI is unavailable", async () => {
    routeFetch(async () =>
      json(503, {
        error: {
          code: "AI_UNAVAILABLE",
          message: "AI analysis isn't available right now. You can fill in the details yourself.",
          details: { reason: "PROVIDER_ERROR" },
        },
      }),
    );
    renderStep(makeComplaint());

    expect(await screen.findByRole("alert")).toHaveTextContent("fill in the details yourself");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();

    // The form still works by hand.
    const title = screen.getByLabelText("Title");
    expect(title).toBeEnabled();
    await userEvent.type(title, "Typed by hand");
    expect(title).toHaveValue("Typed by hand");

    // Retrying calls the AI again.
    routeFetch(async () => json(201, analysis));
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByText("Demo AI")).toBeInTheDocument());
    expect(title).toHaveValue("Typed by hand");
  });
});
