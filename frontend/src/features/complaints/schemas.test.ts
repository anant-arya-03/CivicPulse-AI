import { describe, expect, it } from "vitest";

import {
  detailsSchema,
  locationSchema,
  MAX_PHOTO_BYTES,
  toDetailsPayload,
  toLocationPayload,
  validatePhotoFile,
  type LocationValues,
} from "@/features/complaints/schemas";

function fakeFile(name: string, type: string, size: number): File {
  const file = new File(["x"], name, { type });
  Object.defineProperty(file, "size", { value: size }); // avoid allocating megabytes in tests
  return file;
}

function firstError(result: { success: boolean; error?: { issues: { message: string }[] } }) {
  return result.error?.issues[0]?.message;
}

describe("validatePhotoFile", () => {
  it.each([
    ["photo.jpg", "image/jpeg"],
    ["photo.png", "image/png"],
    ["photo.webp", "image/webp"],
  ])("accepts %s", (name, type) => {
    expect(validatePhotoFile(fakeFile(name, type, 500_000))).toBeNull();
  });

  it("accepts a photo of exactly the maximum size", () => {
    expect(validatePhotoFile(fakeFile("big.jpg", "image/jpeg", MAX_PHOTO_BYTES))).toBeNull();
  });

  it("rejects a photo over 10 MB", () => {
    expect(validatePhotoFile(fakeFile("big.jpg", "image/jpeg", MAX_PHOTO_BYTES + 1))).toMatch(
      /larger than 10 MB/,
    );
  });

  it("explains HEIC photos from iPhones", () => {
    expect(validatePhotoFile(fakeFile("IMG_1234.HEIC", "", 1000))).toMatch(/HEIC/);
    expect(validatePhotoFile(fakeFile("x.heic", "image/heic", 1000))).toMatch(/HEIC/);
  });

  it.each([
    ["anim.gif", "image/gif"],
    ["doc.pdf", "application/pdf"],
    ["photo.jpg", ""],
  ])("rejects %s (%s)", (name, type) => {
    expect(validatePhotoFile(fakeFile(name, type, 1000))).toBe(
      "Please choose a JPEG, PNG, or WebP photo.",
    );
  });

  it("rejects an empty file", () => {
    expect(validatePhotoFile(fakeFile("p.jpg", "image/jpeg", 0))).toBe("This file is empty.");
  });
});

describe("detailsSchema", () => {
  const valid = {
    title: "Deep pothole near school",
    category: "ROAD_POTHOLE",
    severity: "HIGH",
    description: "A large pothole that cars swerve around.",
    observedAt: "",
  };

  it("accepts valid details", () => {
    expect(detailsSchema.safeParse(valid).success).toBe(true);
  });

  it("requires a category", () => {
    expect(firstError(detailsSchema.safeParse({ ...valid, category: "" }))).toBe(
      "Choose the type of issue.",
    );
  });

  it("requires a meaningful title and description", () => {
    expect(firstError(detailsSchema.safeParse({ ...valid, title: "Hole" }))).toMatch(/at least 5/);
    expect(firstError(detailsSchema.safeParse({ ...valid, description: "bad" }))).toMatch(
      /at least 10/,
    );
  });

  it("trims whitespace", () => {
    const parsed = detailsSchema.parse({ ...valid, title: "   Deep pothole near school  " });
    expect(parsed.title).toBe("Deep pothole near school");
  });

  it("rejects an observation date in the future", () => {
    expect(firstError(detailsSchema.safeParse({ ...valid, observedAt: "2999-01-01T10:00" }))).toBe(
      "The date can't be in the future.",
    );
  });

  it("builds the API payload", () => {
    const payload = toDetailsPayload(detailsSchema.parse({ ...valid, observedAt: "2026-01-15T09:30" }));
    expect(payload).toMatchObject({ title: valid.title, category: "ROAD_POTHOLE", severity: "HIGH" });
    expect(payload.observed_at).toBe(new Date("2026-01-15T09:30").toISOString());
    expect(toDetailsPayload(detailsSchema.parse(valid)).observed_at).toBeNull();
  });
});

describe("locationSchema", () => {
  const valid: LocationValues = {
    addressLine: "45 Lake Road",
    locality: "Lakeside",
    city: "Demo City",
    state: "",
    postalCode: "",
    country: "in",
    latitude: 12.97,
    longitude: 77.59,
    confirmed: true,
  };

  it("accepts a valid location", () => {
    expect(locationSchema.safeParse(valid).success).toBe(true);
  });

  it("works without a map pin", () => {
    expect(locationSchema.safeParse({ ...valid, latitude: null, longitude: null }).success).toBe(
      true,
    );
  });

  it("requires explicit confirmation", () => {
    expect(firstError(locationSchema.safeParse({ ...valid, confirmed: false }))).toBe(
      "Please confirm this is where the problem is.",
    );
  });

  it("requires an address and a city", () => {
    expect(firstError(locationSchema.safeParse({ ...valid, addressLine: "" }))).toMatch(/street address/);
    expect(firstError(locationSchema.safeParse({ ...valid, city: " " }))).toBe("Enter the city or town.");
  });

  it("rejects an incomplete pin", () => {
    expect(firstError(locationSchema.safeParse({ ...valid, longitude: null }))).toMatch(/pin/);
  });

  it("rejects a country that isn't a 2-letter code", () => {
    expect(firstError(locationSchema.safeParse({ ...valid, country: "India" }))).toBe(
      "Use a 2-letter country code.",
    );
  });

  it("builds the API payload with confirmation and empty fields as null", () => {
    expect(toLocationPayload(locationSchema.parse(valid))).toEqual({
      address_line: "45 Lake Road",
      locality: "Lakeside",
      city: "Demo City",
      state: null,
      postal_code: null,
      country: "IN",
      latitude: 12.97,
      longitude: 77.59,
      confirm_location: true,
    });
  });
});
