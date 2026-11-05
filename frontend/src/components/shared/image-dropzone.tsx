"use client";

import { ImageUp } from "lucide-react";
import { useId, useState, type DragEvent } from "react";

import { useHydrated } from "@/lib/hydration";
import { cn } from "@/lib/utils";

interface ImageDropzoneProps {
  onFile: (file: File) => void;
  accept: string;
  hint: string;
  disabled?: boolean;
  error?: string | null;
}

/** Drag a photo here, or click / press Enter to open the file picker (camera on phones). */
export function ImageDropzone({ onFile, accept, hint, disabled: disabledProp, error }: ImageDropzoneProps) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);
  // The input exists in the prerendered HTML before React is ready to handle it. A file chosen
  // in that moment would be silently lost, so stay disabled until the page is interactive.
  const hydrated = useHydrated();
  const disabled = disabledProp || !hydrated;

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  }

  return (
    <div className="grid gap-2">
      <label
        htmlFor={inputId}
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-12 text-center transition-colors",
          "focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2",
          dragging ? "border-teal bg-teal-soft" : "border-input bg-card hover:border-teal hover:bg-teal-soft/40",
          error && "border-error",
          disabled && "pointer-events-none opacity-60",
        )}
      >
        <span className="flex size-14 items-center justify-center rounded-2xl bg-teal-soft text-teal">
          <ImageUp className="size-7" aria-hidden />
        </span>
        <span className="text-base font-semibold text-navy">
          Drag a photo here, or <span className="text-teal-strong underline">browse</span>
        </span>
        <span className="text-sm text-muted-foreground">{hint}</span>
        <input
          id={inputId}
          type="file"
          accept={accept}
          disabled={disabled}
          className="sr-only"
          aria-describedby={error ? `${inputId}-error` : undefined}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onFile(file);
            event.target.value = ""; // allow choosing the same file again after an error
          }}
        />
      </label>
      {error && (
        <p id={`${inputId}-error`} role="alert" className="text-sm text-error-strong">
          {error}
        </p>
      )}
    </div>
  );
}
