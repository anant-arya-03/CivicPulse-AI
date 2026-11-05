"use client";

import { FastForward, FlaskConical, MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { useAdvanceTime, useSimulateReply, useSimulationInfo } from "@/features/complaints/hooks";
import { isApiError } from "@/lib/api-client";
import type { Complaint } from "@/types/api";

/**
 * Development/demo only: shown when the backend runs with ENABLE_SIMULATION=true.
 * Creates simulated department replies and skips ahead to the next deadline check.
 */
export function DemoTools({ complaint }: { complaint: Complaint }) {
  const { data: info } = useSimulationInfo();
  const simulateReply = useSimulateReply(complaint.id);
  const advance = useAdvanceTime(complaint.id);
  const [scenario, setScenario] = useState("acknowledged");

  if (!info?.enabled || !complaint.submitted_at || complaint.status === "CANCELLED") return null;

  const onError = (error: unknown) =>
    toast.error(isApiError(error) ? error.message : "Something went wrong. Please try again.");

  return (
    <Card className="border-dashed border-warning">
      <CardHeader>
        <CardTitle>
          <h2 className="flex items-center gap-2 text-base">
            <FlaskConical className="size-4 text-warning-strong" aria-hidden /> Demo tools
          </h2>
        </CardTitle>
        <CardDescription>
          For demonstrations only. These create simulated replies and skip ahead in time.
          Nothing real is sent or received.
        </CardDescription>
      </CardHeader>
      <CardContent className="grid grid-cols-1 gap-4">
        <div className="grid gap-2">
          <Label htmlFor="demo-reply">Simulated reply from the department</Label>
          <select
            id="demo-reply"
            value={scenario}
            onChange={(event) => setScenario(event.target.value)}
            className="h-10 w-full min-w-0 rounded-lg border border-input bg-background px-3 text-sm"
          >
            {info.reply_scenarios.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
          <Button
            type="button"
            variant="outline"
            disabled={simulateReply.isPending}
            onClick={() =>
              simulateReply.mutate(scenario, {
                onSuccess: () => toast.success("Simulated reply received."),
                onError,
              })
            }
          >
            <MessageSquarePlus aria-hidden /> Simulate reply
          </Button>
        </div>
        <Button
          type="button"
          variant="outline"
          disabled={advance.isPending}
          onClick={() =>
            advance.mutate(undefined, {
              onSuccess: (result) =>
                toast.success(result.ran[0]?.outcome ?? "Ran the next scheduled check."),
              onError,
            })
          }
        >
          <FastForward aria-hidden /> Skip ahead to the next check
        </Button>
      </CardContent>
    </Card>
  );
}
