import type { Metadata } from "next";
import { Suspense } from "react";

import { ReportWizard, WizardSkeleton } from "@/features/complaints/report-wizard/report-wizard";

export const metadata: Metadata = { title: "Report an issue" };

export default function ReportPage() {
  return (
    // The wizard reads ?draft= and ?step= from the URL, which needs a Suspense boundary.
    <Suspense fallback={<WizardSkeleton />}>
      <ReportWizard />
    </Suspense>
  );
}
