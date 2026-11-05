/**
 * Validation for the report wizard. Rules mirror backend/app/modules/complaints/schemas.py
 * and backend/app/modules/evidence/image_validation.py. The backend validates again.
 */

import { z } from "zod";

import { CATEGORIES, SEVERITIES } from "@/features/complaints/constants";
import type { ComplaintUpdatePayload } from "@/types/api";

// ── Photo ───────────────────────────────────────────────────────────────────

export const MAX_PHOTO_MB = 10;
export const MAX_PHOTO_BYTES = MAX_PHOTO_MB * 1024 * 1024;
export const ACCEPTED_PHOTO_TYPES = ["image/jpeg", "image/png", "image/webp"] as const;

/** Quick checks before uploading. Returns an error message, or null if the file looks fine. */
export function validatePhotoFile(file: File): string | null {
  const name = file.name.toLowerCase();
  if (file.type === "image/heic" || file.type === "image/heif" || /\.(heic|heif)$/.test(name)) {
    return "HEIC photos aren't supported yet. Please export the photo as JPEG and try again.";
  }
  if (!(ACCEPTED_PHOTO_TYPES as readonly string[]).includes(file.type)) {
    return "Please choose a JPEG, PNG, or WebP photo.";
  }
  if (file.size === 0) return "This file is empty.";
  if (file.size > MAX_PHOTO_BYTES) {
    return `This photo is larger than ${MAX_PHOTO_MB} MB. Please choose a smaller one.`;
  }
  return null;
}

// ── Step 2: details ─────────────────────────────────────────────────────────

export const detailsSchema = z.object({
  title: z
    .string()
    .trim()
    .min(5, "Give the issue a short title (at least 5 characters).")
    .max(160, "Keep the title under 160 characters."),
  category: z.enum(CATEGORIES, { error: "Choose the type of issue." }),
  severity: z.enum(SEVERITIES),
  description: z
    .string()
    .trim()
    .min(10, "Describe the problem in a sentence or two (at least 10 characters).")
    .max(5000, "Keep the description under 5000 characters."),
  /** From <input type="datetime-local">, e.g. "2026-11-03T09:30". Optional. */
  observedAt: z
    .string()
    .refine((value) => !value || !Number.isNaN(new Date(value).getTime()), "Enter a valid date.")
    .refine(
      (value) => !value || new Date(value).getTime() <= Date.now() + 5 * 60_000,
      "The date can't be in the future.",
    ),
});

export type DetailsValues = z.infer<typeof detailsSchema>;

export function toDetailsPayload(values: DetailsValues): ComplaintUpdatePayload {
  return {
    title: values.title,
    category: values.category,
    severity: values.severity,
    description: values.description,
    // datetime-local has no time zone; new Date() reads it as the user's local time.
    observed_at: values.observedAt ? new Date(values.observedAt).toISOString() : null,
  };
}

// ── Step 5: the complaint letter ───────────────────────────────────────────
// Mirrors draft_subject / draft_body in backend/app/modules/complaints/schemas.py.

export const letterSchema = z.object({
  subject: z
    .string()
    .trim()
    .min(5, "The subject needs at least 5 characters.")
    .max(200, "Keep the subject under 200 characters."),
  body: z
    .string()
    .trim()
    .min(20, "The letter needs at least 20 characters.")
    .max(10000, "Keep the letter under 10,000 characters."),
});

export type LetterValues = z.infer<typeof letterSchema>;

/** A follow-up reminder the citizen edits before approving (same limits as the backend). */
export const reminderSchema = z.object({
  subject: z
    .string()
    .trim()
    .min(5, "The subject needs at least 5 characters.")
    .max(200, "Keep the subject under 200 characters."),
  body: z
    .string()
    .trim()
    .min(20, "The reminder needs at least 20 characters.")
    .max(10000, "Keep the reminder under 10,000 characters."),
});
export type ReminderValues = z.infer<typeof reminderSchema>;

// ── Step 3: location ────────────────────────────────────────────────────────

const optionalText = (max: number) =>
  z.string().trim().max(max, `Keep this under ${max} characters.`);

export const locationSchema = z
  .object({
    addressLine: z
      .string()
      .trim()
      .min(3, "Enter the street address or a nearby landmark.")
      .max(255, "Keep the address under 255 characters."),
    locality: optionalText(120),
    city: z.string().trim().min(2, "Enter the city or town.").max(120),
    state: optionalText(120),
    postalCode: optionalText(20),
    country: z
      .string()
      .trim()
      .refine((value) => value === "" || /^[A-Za-z]{2}$/.test(value), "Use a 2-letter country code."),
    latitude: z.number().min(-90).max(90).nullable(),
    longitude: z.number().min(-180).max(180).nullable(),
    confirmed: z.boolean().refine((value) => value, "Please confirm this is where the problem is."),
  })
  .refine((v) => (v.latitude === null) === (v.longitude === null), {
    message: "The map pin is incomplete. Place it again.",
    path: ["latitude"],
  });

export type LocationValues = z.infer<typeof locationSchema>;

export function toLocationPayload(values: LocationValues): ComplaintUpdatePayload {
  const orNull = (text: string) => text.trim() || null;
  return {
    address_line: values.addressLine,
    locality: orNull(values.locality),
    city: values.city,
    state: orNull(values.state),
    postal_code: orNull(values.postalCode),
    country: values.country ? values.country.toUpperCase() : null,
    latitude: values.latitude,
    longitude: values.longitude,
    confirm_location: true,
  };
}
