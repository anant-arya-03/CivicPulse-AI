import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { DepartmentStep } from "./department-step";
import type { Authority, Complaint } from "@/types/api";

const department = {
  id: "demo-roads", name: "Demo City Roads Department", jurisdiction: "Demo City",
  city: "Demo City", country: "XX", is_demo: true, official_email: "roads@demo-city.example",
  supported_categories: ["ROAD_POTHOLE"],
} as Authority;
const complaint = { id: "c1", city: "Noida", country: "IN", category: "ROAD_POTHOLE", authority: null } as Complaint;
const fetchMock = vi.fn<typeof fetch>();
afterEach(() => { fetchMock.mockReset(); vi.unstubAllGlobals(); });

function setup({ enabled = true, saved = false, fail = false } = {}) {
  const next = vi.fn();
  let failDirectory = fail;
  const current = saved ? { ...complaint, authority: department } : complaint;
  fetchMock.mockImplementation(async (input, init) => {
    const url = String(input);
    if (url.endsWith("/simulation")) return Response.json({ enabled, reply_scenarios: [] });
    if (url.endsWith("/authority-matches")) return Response.json({ confidence: "NONE", matches: [], selected_authority_id: saved ? department.id : null });
    if (url.includes("/authorities?")) {
      if (failDirectory) { failDirectory = false; return Response.json({ error: { message: "Unavailable" } }, { status: 503 }); }
      return Response.json([department, { ...department, id: "real", name: "Different city's real department", is_demo: false }]);
    }
    if (url.endsWith("/authority") && init?.method === "PUT") return Response.json({ ...complaint, authority: department });
    return Response.json({}, { status: 404 });
  });
  vi.stubGlobal("fetch", fetchMock);
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
    <DepartmentStep complaint={current} onBack={() => {}} onContinue={next} />
  </QueryClientProvider>);
  return next;
}

it("lets a citizen explicitly select a fictional department without changing their location", async () => {
  const next = setup();
  await userEvent.click(await screen.findByRole("button", { name: "Show demo departments" }));
  const radio = await screen.findByRole("radio", { name: "Choose Demo City Roads Department" });
  expect(radio).not.toBeChecked();
  expect(screen.queryByText("Different city's real department")).not.toBeInTheDocument();
  expect(screen.getByText(/Your entered location stays unchanged/)).toBeVisible();
  await userEvent.click(radio);
  await userEvent.click(screen.getByRole("button", { name: "Use demo department" }));
  await waitFor(() => expect(next).toHaveBeenCalledOnce());
  const writes = fetchMock.mock.calls.filter(([, init]) => init?.method && init.method !== "GET");
  expect(writes).toHaveLength(1);
  expect(writes[0][1]).toMatchObject({ method: "PUT", body: JSON.stringify({ authority_id: department.id }) });
});

it("keeps the manual path when simulation is disabled", async () => {
  setup({ enabled: false });
  expect(await screen.findByRole("button", { name: "Continue without a department" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "Show demo departments" })).not.toBeInTheDocument();
});

it("offers retry when the demo directory cannot load", async () => {
  setup({ fail: true });
  await userEvent.click(await screen.findByRole("button", { name: "Show demo departments" }));
  expect(await screen.findByText("Couldn't load the directory. Please try again.")).toBeVisible();
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(await screen.findByRole("radio", { name: "Choose Demo City Roads Department" })).toBeVisible();
});

it("shows a previously selected demo department when reopening a nonmatching draft", async () => {
  setup({ saved: true });
  const radio = await screen.findByRole("radio", { name: "Choose Demo City Roads Department" });
  await waitFor(() => expect(radio).toBeChecked());
  expect(screen.getByRole("button", { name: "Use demo department" })).toBeVisible();
});
