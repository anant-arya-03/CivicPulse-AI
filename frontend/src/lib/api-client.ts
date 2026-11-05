/**
 * The single place where the frontend talks to the backend.
 *
 * - Calls relative `/api/v1/...` URLs; Next.js forwards them to FastAPI (see next.config.ts).
 * - Adds the `X-CSRF-Token` header to state-changing requests.
 * - Turns the backend's error shape `{ error: { code, message, details } }` into an `ApiError`.
 */

import type { ApiErrorBody } from "@/types/api";

export const API_BASE = "/api/v1";
export const CSRF_COOKIE_NAME = "cp_csrf";

const UNSAFE_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const FALLBACK_MESSAGE = "Something went wrong. Please try again.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}

export function readCookie(name: string): string | undefined {
  if (typeof document === "undefined") return undefined;
  const match = document.cookie.split("; ").find((part) => part.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : undefined;
}

type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

interface RequestOptions {
  method?: HttpMethod;
  body?: unknown;
  signal?: AbortSignal;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, signal } = options;

  const headers: Record<string, string> = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (UNSAFE_METHODS.has(method)) {
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      credentials: "same-origin",
      signal,
    });
  } catch (error) {
    if (signal?.aborted) throw error;
    throw new ApiError(0, "NETWORK_ERROR", "Can't reach the server. Check your connection and try again.");
  }

  if (response.status === 204) return undefined as T;

  const data: unknown = await response.json().catch(() => null);

  if (!response.ok) {
    const error = (data as Partial<ApiErrorBody> | null)?.error;
    throw new ApiError(
      response.status,
      error?.code ?? "HTTP_ERROR",
      error?.message ?? FALLBACK_MESSAGE,
      error?.details ?? {},
    );
  }

  return data as T;
}

interface UploadOptions {
  /** Called with a number from 0 to 100 as the file is sent. */
  onProgress?: (percent: number) => void;
  signal?: AbortSignal;
}

/**
 * Upload a file as multipart/form-data (field name "file").
 * Uses XMLHttpRequest instead of fetch because only XHR reports upload progress.
 */
export function uploadFile<T>(path: string, file: File, options: UploadOptions = {}): Promise<T> {
  const { onProgress, signal } = options;

  return new Promise<T>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}${path}`);
    xhr.withCredentials = true;
    xhr.setRequestHeader("Accept", "application/json");
    const csrfToken = readCookie(CSRF_COOKIE_NAME);
    if (csrfToken) xhr.setRequestHeader("X-CSRF-Token", csrfToken);

    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      let data: unknown = null;
      try {
        data = JSON.parse(xhr.responseText);
      } catch {
        // non-JSON response (e.g. a proxy error page)
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(data as T);
        return;
      }
      const error = (data as Partial<ApiErrorBody> | null)?.error;
      reject(
        new ApiError(
          xhr.status,
          error?.code ?? "HTTP_ERROR",
          error?.message ?? FALLBACK_MESSAGE,
          error?.details ?? {},
        ),
      );
    };
    xhr.onerror = () =>
      reject(new ApiError(0, "NETWORK_ERROR", "The upload failed. Check your connection and try again."));
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    signal?.addEventListener("abort", () => xhr.abort());

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => apiRequest<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => apiRequest<T>(path, { method: "PUT", body }),
  delete: <T>(path: string) => apiRequest<T>(path, { method: "DELETE" }),
};
