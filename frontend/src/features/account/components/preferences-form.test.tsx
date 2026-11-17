import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { PreferencesForm } from "./preferences-form";
const user = { id: "u1", name: "Citizen", email: "citizen@example.com", created_at: "2026-11-17" };
afterEach(() => vi.unstubAllGlobals());
it("persists explicit privacy choices and explains existing drafts", async () => {
  let payload: unknown;
  vi.stubGlobal("fetch", vi.fn(async (_url, init) => { payload = JSON.parse(init.body); return new Response(JSON.stringify(user)); }));
  render(<QueryClientProvider client={new QueryClient()}><PreferencesForm user={user} /></QueryClientProvider>);
  await userEvent.click(screen.getByLabelText("Include map coordinates in new letters"));
  await userEvent.click(screen.getByRole("button", { name: "Save preferences" }));
  await waitFor(() => expect(payload).toMatchObject({ privacy_settings: { share_exact_coordinates: false, include_name_in_complaints: true } }));
  expect(screen.getByText(/Existing drafts and messages keep their text/)).toBeVisible();
});
