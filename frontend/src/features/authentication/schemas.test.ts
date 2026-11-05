import { describe, expect, it } from "vitest";

import { loginSchema, registerSchema } from "@/features/authentication/schemas";

const validRegistration = {
  name: "Asha Rao",
  email: "asha@example.com",
  password: "Secret123",
  confirmPassword: "Secret123",
};

function firstError(result: { success: boolean; error?: { issues: { message: string }[] } }) {
  return result.error?.issues[0]?.message;
}

describe("loginSchema", () => {
  it("accepts a valid email and password", () => {
    expect(loginSchema.safeParse({ email: "asha@example.com", password: "x" }).success).toBe(true);
  });

  it("trims whitespace around the email", () => {
    const result = loginSchema.parse({ email: "  asha@example.com ", password: "x" });
    expect(result.email).toBe("asha@example.com");
  });

  it("rejects an empty email with a helpful message", () => {
    expect(firstError(loginSchema.safeParse({ email: "", password: "x" }))).toBe(
      "Enter your email address.",
    );
  });

  it("rejects an invalid email", () => {
    expect(firstError(loginSchema.safeParse({ email: "not-an-email", password: "x" }))).toBe(
      "Enter a valid email address.",
    );
  });

  it("requires a password", () => {
    expect(firstError(loginSchema.safeParse({ email: "asha@example.com", password: "" }))).toBe(
      "Enter your password.",
    );
  });
});

describe("registerSchema", () => {
  it("accepts a valid registration", () => {
    expect(registerSchema.safeParse(validRegistration).success).toBe(true);
  });

  it.each([
    ["Short1", "Use at least 8 characters."],
    ["lettersonly", "Include at least one number."],
    ["12345678", "Include at least one letter."],
  ])("rejects weak password %s", (password, message) => {
    const result = registerSchema.safeParse({
      ...validRegistration,
      password,
      confirmPassword: password,
    });
    expect(firstError(result)).toBe(message);
  });

  it("requires matching passwords", () => {
    const result = registerSchema.safeParse({ ...validRegistration, confirmPassword: "Other123" });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0]?.path).toEqual(["confirmPassword"]);
    expect(firstError(result)).toBe("Passwords don't match.");
  });

  it("requires a name of at least 2 characters", () => {
    expect(firstError(registerSchema.safeParse({ ...validRegistration, name: " A " }))).toBe(
      "Enter your full name (at least 2 characters).",
    );
  });
});
