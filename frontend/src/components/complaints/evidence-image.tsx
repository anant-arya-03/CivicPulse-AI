"use client";

import { ImageOff } from "lucide-react";
import { useState } from "react";

import { cn } from "@/lib/utils";

interface EvidenceImageProps {
  src: string | null;
  alt: string;
  className?: string;
}

/**
 * Shows a complaint photo from the private evidence endpoint.
 *
 * A plain <img> (not next/image) because the image needs the user's session cookie and
 * must never be cached by an optimisation server shared between users.
 */
export function EvidenceImage({ src, alt, className }: EvidenceImageProps) {
  const [failed, setFailed] = useState(false);

  if (!src || failed) {
    return (
      <div
        className={cn("flex items-center justify-center bg-muted text-muted-foreground", className)}
        role="img"
        aria-label={src ? `${alt} (couldn't load)` : "No photo"}
      >
        <ImageOff className="size-6" aria-hidden />
      </div>
    );
  }

  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={src}
      alt={alt}
      loading="lazy"
      onError={() => setFailed(true)}
      className={cn("object-cover", className)}
    />
  );
}
