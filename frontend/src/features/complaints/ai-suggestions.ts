/**
 * How AI suggestions meet the citizen's own input (report step 2).
 *
 * The rule: AI suggestions never overwrite what the citizen typed.
 * - A field the citizen left empty (and hasn't touched) is filled with the suggestion.
 * - A field the citizen filled in keeps their value. If the AI suggests something different,
 *   the suggestion is offered next to it as an optional "Use suggestion".
 */

import type { DetailsValues } from "@/features/complaints/schemas";
import type { VisionAnalysis } from "@/types/api";

export type SuggestibleField = "title" | "category" | "severity" | "description";

export const SUGGESTIBLE_FIELDS: SuggestibleField[] = ["title", "category", "severity", "description"];

export interface SuggestionPlan {
  /** Empty fields to fill with the AI's suggestion. */
  fill: Partial<Pick<DetailsValues, SuggestibleField>>;
  /** Fields the citizen already filled where the AI suggests something different. */
  alternatives: Partial<Pick<DetailsValues, SuggestibleField>>;
}

export function suggestedValues(analysis: VisionAnalysis): Pick<DetailsValues, SuggestibleField> {
  return {
    title: analysis.suggested_title,
    category: analysis.category,
    severity: analysis.severity,
    description: analysis.suggested_description,
  };
}

/** True when a field holds nothing the citizen chose ("Not sure" is the severity default). */
function isEmpty(field: SuggestibleField, value: string | undefined): boolean {
  if (field === "severity") return !value || value === "UNKNOWN";
  return !value || value.trim() === "";
}

export function planSuggestions(
  current: Partial<Pick<DetailsValues, SuggestibleField>>,
  touched: Partial<Record<SuggestibleField, boolean>>,
  analysis: VisionAnalysis,
): SuggestionPlan {
  const suggestion = suggestedValues(analysis);
  const plan: SuggestionPlan = { fill: {}, alternatives: {} };

  for (const field of SUGGESTIBLE_FIELDS) {
    const value = current[field];
    const suggested = suggestion[field];
    const citizensValue = touched[field] || !isEmpty(field, value);

    if (!citizensValue) {
      // TypeScript can't relate the field name to the value type in a loop.
      (plan.fill as Record<SuggestibleField, string>)[field] = suggested;
    } else if (value?.trim() !== suggested.trim() && !(field === "severity" && suggested === "UNKNOWN")) {
      (plan.alternatives as Record<SuggestibleField, string>)[field] = suggested;
    }
  }
  return plan;
}
