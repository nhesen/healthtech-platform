"use client";

export type SessionRole = "PATIENT" | "DOCTOR" | "HOSPITAL_ADMIN";
export interface Session { id: string; name: string; email: string; role: SessionRole }

const KEY = "digisolution.web.session";

export const ROLE_LABELS: Record<SessionRole, string> = { PATIENT: "Vətəndaş", DOCTOR: "Həkim", HOSPITAL_ADMIN: "Xəstəxana" };
export const ROLE_SEGMENTS: Record<SessionRole, string> = { PATIENT: "patient", DOCTOR: "doctor", HOSPITAL_ADMIN: "admin" };
export const ROLE_LANDING: Record<SessionRole, string> = { PATIENT: "/patient/health", DOCTOR: "/doctor/patients", HOSPITAL_ADMIN: "/admin/command-center" };

export function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Session;
    return value?.email && Object.prototype.hasOwnProperty.call(ROLE_LABELS, value?.role) ? value : null;
  } catch { return null; }
}

export function writeSession(session: Session) {
  if (typeof window !== "undefined") window.localStorage.setItem(KEY, JSON.stringify(session));
}

export function clearSession() {
  if (typeof window !== "undefined") window.localStorage.removeItem(KEY);
}
