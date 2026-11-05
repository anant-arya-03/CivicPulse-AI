"use client";

import { ChevronLeft, ChevronRight, ListChecks, Plus, Search, SearchX, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { ComplaintCard } from "@/components/complaints/complaint-card";
import { PageHeader } from "@/components/layout/page-header";
import { EmptyState } from "@/components/shared/empty-state";
import { ErrorState } from "@/components/shared/error-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type { ComplaintListParams, ComplaintSort } from "@/features/complaints/api";
import { CATEGORIES, CATEGORY_META, STATUSES, STATUS_META } from "@/features/complaints/constants";
import { useComplaintList } from "@/features/complaints/hooks";
import { isApiError } from "@/lib/api-client";
import type { Category, ComplaintStatus } from "@/types/api";

const PAGE_SIZE = 10;
const ALL = "all"; // Radix Select needs a non-empty value for the "no filter" option

const SORT_OPTIONS: { value: ComplaintSort; label: string }[] = [
  { value: "-created_at", label: "Newest first" },
  { value: "created_at", label: "Oldest first" },
  { value: "-updated_at", label: "Recently updated" },
];

function oneOf<T extends string>(value: string | null, allowed: readonly T[]): T | undefined {
  return allowed.includes(value as T) ? (value as T) : undefined;
}

/** Read filters from the URL, so they survive a refresh and can be shared as a link. */
function readParams(searchParams: URLSearchParams): ComplaintListParams {
  const page = Number(searchParams.get("page"));
  return {
    search: searchParams.get("search")?.trim() || undefined,
    category: oneOf<Category>(searchParams.get("category"), CATEGORIES),
    status: oneOf<ComplaintStatus>(searchParams.get("status"), STATUSES),
    sort: oneOf(searchParams.get("sort"), SORT_OPTIONS.map((o) => o.value)) ?? "-created_at",
    page: Number.isInteger(page) && page > 0 ? page : 1,
    pageSize: PAGE_SIZE,
  };
}

export function ComplaintListView() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const params = readParams(searchParams);
  const [searchText, setSearchText] = useState(params.search ?? "");

  const { data, isPending, isError, error, refetch, isPlaceholderData } = useComplaintList(params);
  const hasFilters = Boolean(params.search || params.category || params.status);

  function updateParams(changes: Record<string, string | undefined>) {
    const next = new URLSearchParams(searchParams.toString());
    for (const [key, value] of Object.entries(changes)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    if (!("page" in changes)) next.delete("page"); // any filter change goes back to page 1
    const query = next.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
  }

  function handleSearch(event: FormEvent) {
    event.preventDefault();
    updateParams({ search: searchText.trim() || undefined });
  }

  function clearFilters() {
    setSearchText("");
    router.replace(pathname, { scroll: false });
  }

  return (
    <div className="grid gap-6">
      <PageHeader
        title="My complaints"
        description="Every issue you've reported, in one place."
        actions={
          <Button asChild size="lg">
            <Link href="/report">
              <Plus aria-hidden /> Report New Issue
            </Link>
          </Button>
        }
      />

      <section aria-label="Filters" className="grid gap-3 rounded-xl border border-border bg-card p-4 shadow-card">
        <form onSubmit={handleSearch} role="search" className="flex gap-2">
          <label htmlFor="complaint-search" className="sr-only">
            Search complaints
          </label>
          <Input
            id="complaint-search"
            value={searchText}
            onChange={(event) => setSearchText(event.target.value)}
            placeholder="Search by title, description, address, or reference"
          />
          <Button type="submit" variant="outline">
            <Search aria-hidden /> <span className="sr-only sm:not-sr-only">Search</span>
          </Button>
        </form>
        <div className="grid gap-3 sm:grid-cols-3">
          <Select
            value={params.category ?? ALL}
            onValueChange={(value) => updateParams({ category: value === ALL ? undefined : value })}
          >
            <SelectTrigger className="w-full" aria-label="Filter by category">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All categories</SelectItem>
              {CATEGORIES.map((value) => (
                <SelectItem key={value} value={value}>
                  {CATEGORY_META[value].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={params.status ?? ALL}
            onValueChange={(value) => updateParams({ status: value === ALL ? undefined : value })}
          >
            <SelectTrigger className="w-full" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {STATUSES.map((value) => (
                <SelectItem key={value} value={value}>
                  {STATUS_META[value].label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={params.sort} onValueChange={(value) => updateParams({ sort: value })}>
            <SelectTrigger className="w-full" aria-label="Sort order">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {hasFilters && (
          <div>
            <Button variant="ghost" size="sm" onClick={clearFilters}>
              <X aria-hidden /> Clear filters
            </Button>
          </div>
        )}
      </section>

      {isPending ? (
        <div className="grid gap-3" aria-busy="true" aria-label="Loading complaints">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-28 rounded-xl" />
          ))}
        </div>
      ) : isError ? (
        <ErrorState
          message={isApiError(error) ? error.message : "Please try again."}
          onRetry={() => refetch()}
        />
      ) : data.total === 0 ? (
        hasFilters ? (
          <EmptyState
            icon={SearchX}
            title="No complaints match your filters"
            description="Try a different search or clear the filters."
            action={<Button variant="outline" onClick={clearFilters}>Clear filters</Button>}
          />
        ) : (
          <EmptyState
            icon={ListChecks}
            title="No complaints yet"
            description="Report a pothole, broken streetlight, or any other civic issue and track it here."
            action={
              <Button asChild>
                <Link href="/report">Report your first issue</Link>
              </Button>
            }
          />
        )
      ) : (
        <section aria-label="Complaints" className="grid gap-4">
          <h2 className="sr-only">Your complaints</h2>
          <p className="text-sm text-muted-foreground" aria-live="polite">
            {data.total} {data.total === 1 ? "complaint" : "complaints"}
          </p>
          <ul className={isPlaceholderData ? "grid gap-3 opacity-60" : "grid gap-3"}>
            {data.items.map((complaint) => (
              <li key={complaint.id}>
                <ComplaintCard complaint={complaint} />
              </li>
            ))}
          </ul>
          {data.total_pages > 1 && (
            <nav aria-label="Pagination" className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                disabled={data.page <= 1}
                onClick={() => updateParams({ page: String(data.page - 1) })}
              >
                <ChevronLeft aria-hidden /> Previous
              </Button>
              <span className="text-sm text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </span>
              <Button
                variant="outline"
                disabled={data.page >= data.total_pages}
                onClick={() => updateParams({ page: String(data.page + 1) })}
              >
                Next <ChevronRight aria-hidden />
              </Button>
            </nav>
          )}
        </section>
      )}
    </div>
  );
}
