import type { Metadata } from "next";
import { Suspense } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { ComplaintDetailView } from "@/features/complaints/components/complaint-detail-view";

export const metadata: Metadata = { title: "Complaint details" };

export default function ComplaintDetailPage() {
  return (
    // The [id] comes from the URL at request time, so useParams needs a Suspense boundary.
    <Suspense fallback={<Skeleton className="h-96 rounded-xl" />}>
      <ComplaintDetailView />
    </Suspense>
  );
}
