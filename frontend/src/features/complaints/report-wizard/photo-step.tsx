"use client";

import { ArrowRight, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { EvidenceImage } from "@/components/complaints/evidence-image";
import { FormAlert } from "@/components/shared/form-alert";
import { ImageDropzone } from "@/components/shared/image-dropzone";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { useCreateComplaint, useDeletePhoto, useUploadPhoto } from "@/features/complaints/hooks";
import {
  ACCEPTED_PHOTO_TYPES,
  MAX_PHOTO_MB,
  validatePhotoFile,
} from "@/features/complaints/schemas";
import { isApiError } from "@/lib/api-client";
import { formatFileSize } from "@/lib/format";
import type { Complaint } from "@/types/api";

interface PhotoStepProps {
  complaint: Complaint | undefined;
  /** Called once, when the first photo creates the draft complaint. */
  onDraftCreated: (complaintId: string) => void;
  onContinue: () => void;
}

const ACCEPT = ACCEPTED_PHOTO_TYPES.join(",");

export function PhotoStep({ complaint, onDraftCreated, onContinue }: PhotoStepProps) {
  const createComplaint = useCreateComplaint();
  const uploadPhoto = useUploadPhoto();
  const deletePhoto = useDeletePhoto();
  const replaceInputRef = useRef<HTMLInputElement>(null);

  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [localPreview, setLocalPreview] = useState<string | null>(null);

  const photo = complaint?.evidence.find((e) => e.evidence_type === "ORIGINAL");
  const uploading = progress !== null;
  const busy = uploading || deletePhoto.isPending;

  // Free the temporary preview URL when it's no longer shown.
  useEffect(() => () => void (localPreview && URL.revokeObjectURL(localPreview)), [localPreview]);

  async function handleFile(file: File) {
    const problem = validatePhotoFile(file);
    if (problem) {
      setError(problem);
      return;
    }
    setError(null);
    setLocalPreview(URL.createObjectURL(file));
    setProgress(0);
    try {
      let complaintId = complaint?.id;
      if (!complaintId) {
        complaintId = (await createComplaint.mutateAsync({})).id;
        onDraftCreated(complaintId);
      }
      await uploadPhoto.mutateAsync({ complaintId, file, onProgress: setProgress });
      // Replacing: remove the old photo only after the new one is safely uploaded.
      if (photo) await deletePhoto.mutateAsync({ complaintId, evidenceId: photo.id });
    } catch (err) {
      setError(isApiError(err) ? err.message : "The upload failed. Please try again.");
    } finally {
      setProgress(null);
      setLocalPreview(null);
    }
  }

  async function handleRemove() {
    if (!complaint || !photo) return;
    setError(null);
    try {
      await deletePhoto.mutateAsync({ complaintId: complaint.id, evidenceId: photo.id });
    } catch (err) {
      setError(isApiError(err) ? err.message : "Couldn't remove the photo. Please try again.");
    }
  }

  const previewSrc = localPreview ?? photo?.url ?? null;

  return (
    <div className="grid grid-cols-1 gap-6">
      <div className="grid gap-1">
        <h2 className="text-xl font-semibold">Upload a photo of the problem</h2>
        <p className="text-sm text-muted-foreground">
          A clear photo helps the department understand the issue. Location data stored inside
          the photo is removed for your privacy.
        </p>
      </div>

      {previewSrc ? (
        <div className="grid grid-cols-1 gap-3">
          <div className="relative overflow-hidden rounded-xl border border-border bg-muted">
            <EvidenceImage
              key={previewSrc}
              src={previewSrc}
              alt="Photo of the reported problem"
              className="aspect-[4/3] w-full object-contain"
            />
            {uploading && (
              <div className="absolute inset-x-0 bottom-0 grid gap-1.5 bg-card/90 p-3 backdrop-blur">
                <div className="flex justify-between text-sm font-medium">
                  <span>Uploading…</span>
                  <span>{progress}%</span>
                </div>
                <Progress value={progress} aria-label="Upload progress" />
              </div>
            )}
          </div>
          {photo && !uploading && (
            <p className="text-xs text-muted-foreground">
              {photo.width} × {photo.height} px · {formatFileSize(photo.file_size_bytes)}
            </p>
          )}
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" disabled={busy} onClick={() => replaceInputRef.current?.click()}>
              <RefreshCw aria-hidden /> Replace photo
            </Button>
            <Button variant="ghost" disabled={busy || !photo} onClick={handleRemove}>
              {deletePhoto.isPending ? <Loader2 className="animate-spin" aria-hidden /> : <Trash2 aria-hidden />}
              Remove
            </Button>
            <input
              ref={replaceInputRef}
              type="file"
              accept={ACCEPT}
              className="sr-only"
              tabIndex={-1}
              aria-hidden
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void handleFile(file);
                event.target.value = "";
              }}
            />
          </div>
          <FormAlert message={error ?? undefined} />
        </div>
      ) : (
        <ImageDropzone
          onFile={(file) => void handleFile(file)}
          accept={ACCEPT}
          hint={`JPEG, PNG, or WebP, up to ${MAX_PHOTO_MB} MB`}
          error={error}
          disabled={busy}
        />
      )}

      <div className="flex justify-end">
        <Button size="lg" onClick={onContinue} disabled={!photo || busy}>
          Continue <ArrowRight aria-hidden />
        </Button>
      </div>
    </div>
  );
}
