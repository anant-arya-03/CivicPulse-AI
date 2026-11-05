"use client";

import { ArrowRight, BellRing, CheckCircle2, Clock, FilePlus2, FolderOpen, Inbox, Plus } from "lucide-react";
import Link from "next/link";

import { ComplaintCard } from "@/components/complaints/complaint-card";
import { ActivityFeed } from "@/components/dashboard/activity-feed";
import { StatCard } from "@/components/dashboard/stat-card";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useCurrentUser } from "@/features/authentication/hooks";
import { useDashboardSummary } from "@/features/complaints/hooks";
import { ATTENTION_META } from "@/features/complaints/monitoring";
import { isApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { AttentionItem } from "@/types/api";

export function DashboardOverview() {
  const { data: user } = useCurrentUser(); // undefined for a moment while loading
  const title = user ? `Welcome, ${user.name.split(" ")[0]}` : "Welcome";
  const { data: summary, isPending, isError, error, refetch } = useDashboardSummary();

  return (
    <div className="grid gap-8">
      <PageHeader
        title={title}
        description="Here's an overview of the civic issues you've reported."
        actions={
          <Button asChild size="lg">
            <Link href="/report">
              <Plus aria-hidden /> Report New Issue
            </Link>
          </Button>
        }
      />

      {isPending ? (
        <DashboardSkeleton />
      ) : isError ? (
        <ErrorState
          message={isApiError(error) ? error.message : "Please try again."}
          onRetry={() => refetch()}
        />
      ) : (
        <>
          <section aria-label="Summary" className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
            <StatCard
              label="Total Complaints"
              value={summary.stats.total}
              icon={FolderOpen}
              tone="navy"
              description={
                summary.stats.drafts
                  ? `${summary.stats.drafts} ${summary.stats.drafts === 1 ? "draft" : "drafts"}`
                  : undefined
              }
            />
            <StatCard label="Active Complaints" value={summary.stats.active} icon={Clock} tone="teal" />
            <StatCard
              label="Pending Responses"
              value={summary.stats.pending_responses}
              icon={Inbox}
              tone="warning"
            />
            <StatCard
              label="Verified Resolutions"
              value={summary.stats.verified_resolutions}
              icon={CheckCircle2}
              tone="success"
            />
          </section>

          {summary.needs_attention.length > 0 && <NeedsAttention items={summary.needs_attention} />}

          {summary.recent_complaints.length === 0 ? (
            <EmptyState
              icon={FilePlus2}
              title="No complaints yet"
              description="When you report a pothole, broken streetlight, or any other civic issue, it will appear here with its latest status."
              action={
                <Button asChild>
                  <Link href="/report">Report your first issue</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <section aria-labelledby="recent-heading" className="grid content-start gap-4">
                <div className="flex items-center justify-between">
                  <h2 id="recent-heading" className="text-xl font-semibold">
                    Recent complaints
                  </h2>
                  <Button asChild variant="link">
                    <Link href="/complaints">
                      View all <ArrowRight aria-hidden />
                    </Link>
                  </Button>
                </div>
                <ul className="grid gap-3">
                  {summary.recent_complaints.map((complaint) => (
                    <li key={complaint.id}>
                      <ComplaintCard complaint={complaint} />
                    </li>
                  ))}
                </ul>
              </section>
              <Card className="h-fit">
                <CardHeader>
                  <CardTitle>
                    <h2 className="text-base">Recent activity</h2>
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <ActivityFeed items={summary.recent_activity} />
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  );
}

const ATTENTION_TONES = {
  warning: "bg-warning-soft text-warning-strong",
  error: "bg-error-soft text-error-strong",
  teal: "bg-teal-soft text-teal-strong",
};

function NeedsAttention({ items }: { items: AttentionItem[] }) {
  return (
    <section aria-labelledby="attention-heading" className="grid gap-3">
      <h2 id="attention-heading" className="flex items-center gap-2 text-xl font-semibold">
        <BellRing className="size-5 text-teal" aria-hidden /> Needs your attention
      </h2>
      <ul className="grid gap-2">
        {items.map((item) => {
          const meta = ATTENTION_META[item.kind];
          return (
            <li key={item.complaint_id}>
              <Link
                href={`/complaints/${item.complaint_id}`}
                className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border bg-card p-4 hover:border-teal"
              >
                <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", ATTENTION_TONES[meta.tone])}>
                  {meta.label}
                </span>
                <span className="font-medium text-navy">{item.complaint_title ?? item.complaint_reference}</span>
                <span className="w-full text-sm text-muted-foreground">{item.message}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function DashboardSkeleton() {
  return (
    <div className="grid gap-6" aria-busy="true" aria-label="Loading dashboard">
      <div className="grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 rounded-xl" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-xl" />
    </div>
  );
}
