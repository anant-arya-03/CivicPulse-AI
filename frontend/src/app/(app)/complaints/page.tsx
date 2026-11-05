import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ComplaintListView } from "@/features/complaints/components/complaint-list-view";

export const metadata: Metadata = { title: "My complaints" };

export default function ComplaintsPage() {
  return (
    // Filters live in the URL (?search=&status=...), which needs a Suspense boundary.
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <ComplaintListView />
    </Suspense>
  );
}
