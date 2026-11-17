"use client";
import { Bell } from "lucide-react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api-client";
import { useHydrationSafeQuery } from "@/lib/hydration";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/shared/error-state";
interface Feed { unread_count: number; items: { id: string; complaint_id: string; description: string; created_at: string; unread: boolean }[] }
export function NotificationBell() {
  const cache = useQueryClient();
  const feed = useHydrationSafeQuery(useQuery({ queryKey: ["notifications"], queryFn: () => api.get<Feed>("/notifications"), refetchInterval: 30000 }));
  const seen = useMutation({ mutationFn: (id: string) => api.post("/notifications/mark-seen", { through_id: id }), onSuccess: () => cache.invalidateQueries({ queryKey: ["notifications"] }) });
  return <details className="relative mb-5 rounded-xl border bg-card p-3">
    <summary className="flex min-h-11 cursor-pointer items-center gap-2 font-medium text-navy"><Bell className="size-5" aria-hidden />Notifications
      {!!feed.data?.unread_count && <span className="rounded-full bg-navy px-2 text-sm text-white">{feed.data.unread_count} unread</span>}
    </summary>
    <section aria-label="Notifications" className="grid gap-3 pt-3">
      {feed.isPending ? <p role="status">Loading updates...</p> : feed.isError ? <ErrorState message="Could not load updates." onRetry={() => feed.refetch()} /> : <>
        {feed.data.items.length === 0 && <p className="text-sm text-muted-foreground">You are all caught up. Replies and reminders will appear here.</p>}
        {!!feed.data.unread_count && <Button className="w-fit" variant="outline" disabled={seen.isPending} onClick={() => seen.mutate(feed.data.items[0].id)}>Mark all as read</Button>}
        <ul className="grid max-h-80 gap-2 overflow-y-auto" tabIndex={0} aria-label="Recent updates">{feed.data.items.map(item => <li key={item.id}>
          <Link className="block rounded-lg border p-3 text-sm hover:bg-secondary focus-visible:ring-2" href={`/complaints/${item.complaint_id}`}>
            {item.unread && <span className="font-semibold text-teal-strong">New: </span>}{item.description}
            <time className="mt-1 block text-xs text-muted-foreground" dateTime={item.created_at}>{new Date(item.created_at).toLocaleString()}</time>
          </Link>
        </li>)}</ul>
      </>}
      {seen.isError && <p role="alert">Could not mark updates as read. Please try again.</p>}
    </section>
  </details>;
}
