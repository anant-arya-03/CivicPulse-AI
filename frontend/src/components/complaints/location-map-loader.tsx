"use client";

import dynamic from "next/dynamic";

import { Skeleton } from "@/components/ui/skeleton";

export type { MapPoint } from "@/components/complaints/location-map";

/** Loads the Leaflet map in the browser only (Leaflet can't run on the server). */
export const LocationMap = dynamic(() => import("@/components/complaints/location-map"), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-64 w-full rounded-xl" />,
});
