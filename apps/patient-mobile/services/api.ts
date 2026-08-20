import { sessionEmail } from "@/services/session";
import type { DemoUser, DocumentUpload, ExtractedLab } from "@/types/api";

export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "").replace(/\/$/, "");
export const DEMO_MODE = process.env.EXPO_PUBLIC_DEMO_MODE !== "false";
const API_TIMEOUT_MS = Number(process.env.EXPO_PUBLIC_API_TIMEOUT_MS ?? "20000");
export const PATIENT_ID = "patient_hasan";
export const HOSPITAL_ID = "hospital_caspian";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

function ensureConfigured() {
  if (!API_URL) throw new ApiError(0, "Set EXPO_PUBLIC_API_URL to the deployed HTTPS API or a local LAN address.");
}

async function responseError(response: Response): Promise<never> {
  let message = "The request could not be completed.";
  try { const body = await response.json(); message = body.detail ?? message; } catch { /* keep safe message */ }
  throw new ApiError(response.status, message);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  ensureConfigured();
  const email = await sessionEmail();
  if (!email) throw new ApiError(401, "Sessiya bitmişdir. Yenidən daxil olun.");
  const headers = new Headers(init.headers);
  headers.set("X-Demo-User", email);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const controller = new AbortController();
  const timeoutMs = path.startsWith("/documents") || path.startsWith("/cv/analyze") ? Math.max(API_TIMEOUT_MS, 120000) : API_TIMEOUT_MS;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${API_URL}${path}`, { ...init, headers, signal: controller.signal });
    if (!response.ok) return responseError(response);
    return response.json() as Promise<T>;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError(0, "The HealthTech service took too long to respond. Please try again.");
    throw new ApiError(0, "Unable to connect to the HealthTech service.");
  } finally {
    clearTimeout(timer);
  }
}

/** FIN sign-in. Runs before a session exists, so it does not send the X-Demo-User header. */
export async function login(fin: string, role: string): Promise<DemoUser> {
  ensureConfigured();
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), API_TIMEOUT_MS);
  try {
    const response = await fetch(`${API_URL}/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ fin, role }), signal: controller.signal });
    if (response.status === 401) throw new ApiError(401, "FIN və rol uyğun gəlmir. 1AZ0001 Vətəndaş, 2AZ0002 Həkim, 3AZ0003 Xəstəxanadır.");
    if (response.status === 404) throw new ApiError(404, "Demo girişi bağlıdır.");
    if (response.status === 422) throw new ApiError(422, "FIN 7 simvoldan ibarət olmalıdır.");
    if (response.status === 429) throw new ApiError(429, "Çox sayda cəhd. Bir az sonra yenidən yoxlayın.");
    if (!response.ok) return responseError(response);
    return response.json() as Promise<DemoUser>;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (controller.signal.aborted) throw new ApiError(0, "Xidmət cavab vermədi. Yenidən yoxlayın.");
    throw new ApiError(0, "HealthTech xidmətinə qoşulmaq mümkün olmadı.");
  } finally {
    clearTimeout(timer);
  }
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

export interface VisionStatus {
  yolo_active: boolean; engine: string | null; model: string | null; device?: string | null;
  identity_recognition: boolean; frames_sent_to_api: boolean; install_hint: string | null;
}
export interface VisionAnalysis {
  yolo_active: boolean; engine?: string; identity_recognition: boolean; frames_discarded?: boolean;
  frames_analyzed?: number; peak_people?: number; average_people?: number; room_id?: string;
  crowding?: { level: string; peak_people: number; average_people: number; explanation: string };
  movement?: { pose_counts: Record<string, number>; transitions: string[]; incoming_people: boolean; fall_risk_signal: boolean; explanation: string };
  latest_people?: { index: number; state: string; confidence: number }[];
  events_posted?: { id: string; status: string }[];
}
export async function uploadVision(asset: UploadAsset, roomId = "204"): Promise<VisionAnalysis> {
  const form = new FormData();
  form.append("file", { uri: asset.uri, name: asset.name, type: asset.mimeType } as unknown as Blob);
  form.append("room_id", roomId);
  return api<VisionAnalysis>("/cv/analyze", { method: "POST", body: form });
}

export async function reviewAndConfirm(documentId: string, results: ExtractedLab[], reportDate?: string, sourceName?: string) {
  const body = { results, report_date: reportDate || null, source_name: sourceName || null };
  await patch(`/documents/${documentId}/review`, body);
  return post<{ status: string; record_id: string; results_created: number }>(`/documents/${documentId}/confirm`, body);
}
