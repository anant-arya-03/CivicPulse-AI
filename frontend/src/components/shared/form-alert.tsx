import { CircleAlert } from "lucide-react";

/** A form-level error banner (e.g. "Incorrect email or password."). */
export function FormAlert({ message }: { message?: string }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-lg border border-error/30 bg-error-soft px-3 py-2.5 text-sm text-error-strong"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0" aria-hidden />
      <span>{message}</span>
    </div>
  );
}
