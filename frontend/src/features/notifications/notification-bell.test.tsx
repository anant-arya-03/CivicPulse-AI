import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { NotificationBell } from "./notification-bell";
afterEach(() => vi.unstubAllGlobals());
it("marks only the displayed snapshot as read and links to the complaint", async () => {
  const requests: string[] = [];
  let unread = 1;
  vi.stubGlobal("fetch", vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") { requests.push(String(init.body)); unread = 0; return new Response(null, { status: 204 }); }
    return new Response(JSON.stringify({ unread_count: unread, items: [{ id: "event-1", complaint_id: "complaint-1", description: "Simulated reply received.", created_at: "2026-11-17T10:00:00Z", unread: !!unread }] }));
  }));
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><NotificationBell /></QueryClientProvider>);
  await userEvent.click(screen.getByText("Notifications"));
  await userEvent.click(await screen.findByRole("button", { name: "Mark all as read" }));
  await waitFor(() => expect(requests).toEqual([JSON.stringify({ through_id: "event-1" })]));
  expect(screen.getByRole("link")).toHaveAttribute("href", "/complaints/complaint-1");
  await waitFor(() => expect(screen.queryByText("1 unread")).not.toBeInTheDocument());
});
