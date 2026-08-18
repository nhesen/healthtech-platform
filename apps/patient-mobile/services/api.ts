import type { DocumentUpload, ExtractedLab } from "@/types/api";

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const DEMO_MODE = process.env.EXPO_PUBLIC_DEMO_MODE !== "false";
export const PATIENT_ID = "patient_hasan";
const DEMO_EMAIL = "patient@demo.az";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function ensureConfigured() {
  if (!API_URL) throw new ApiError(0, "Set EXPO_PUBLIC_API_URL to the backend LAN address.");
}

async function responseError(response: Response): Promise<never> {
  let message = "The request could not be completed.";
  try { const body = await response.json(); message = body.detail ?? message; } catch { /* keep safe message */ }
  throw new ApiError(response.status, message);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  ensureConfigured();
  const headers = new Headers(init.headers);
  headers.set("X-Demo-User", DEMO_EMAIL);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!response.ok) return responseError(response);
  return response.json() as Promise<T>;
}

export function post<T>(path: string, body?: unknown) {
  return api<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}
export function patch<T>(path: string, body?: unknown) {
  return api<T>(path, { method: "PATCH", body: body === undefined ? undefined : JSON.stringify(body) });
}

export interface UploadAsset { uri: string; name: string; mimeType: string }
export async function uploadDocument(asset: UploadAsset): Promise<DocumentUpload> {
  const form = new FormData();
  form.append("file", { uri: asset.uri, name: asset.name, type: asset.mimeType } as unknown as Blob);
  return api<DocumentUpload>(`/documents/upload?patient_id=${PATIENT_ID}`, { method: "POST", body: form });
}

export async function reviewAndConfirm(documentId: string, results: ExtractedLab[], reportDate?: string, sourceName?: string) {
  const body = { results, report_date: reportDate || null, source_name: sourceName || null };
  await patch(`/documents/${documentId}/review`, body);
  return post<{ status: string; record_id: string; results_created: number }>(`/documents/${documentId}/confirm`, body);
}
