import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { DemoRole, DemoUser } from "@/types/api";

const KEY = "healthtech.patient.session";

export const ROLE_LABELS: Record<DemoRole, string> = { PATIENT: "Vətəndaş", DOCTOR: "Həkim", HOSPITAL_ADMIN: "Xəstəxana" };
export const ROLE_HOME = { PATIENT: "/(tabs)", DOCTOR: "/doctor", HOSPITAL_ADMIN: "/admin" } as const;
export type RoleHome = (typeof ROLE_HOME)[DemoRole];

let cached: DemoUser | null | undefined;

async function readRaw() {
  if (Platform.OS === "web") return localStorage.getItem(KEY);
  return SecureStore.getItemAsync(KEY);
}

async function writeRaw(value: string | null) {
  if (Platform.OS === "web") {
    if (value) localStorage.setItem(KEY, value); else localStorage.removeItem(KEY);
    return;
  }
  if (value) await SecureStore.setItemAsync(KEY, value); else await SecureStore.deleteItemAsync(KEY);
}

export async function getSession(): Promise<DemoUser | null> {
  if (cached !== undefined) return cached;
  const raw = await readRaw();
  if (!raw) { cached = null; return cached; }
  try {
    const value = JSON.parse(raw) as DemoUser;
    cached = value?.email ? value : null;
  } catch { cached = null; }
  return cached;
}

export async function setSession(user: DemoUser) {
  cached = user;
  await writeRaw(JSON.stringify(user));
  return user;
}

export async function clearSession() {
  cached = null;
  await writeRaw(null);
}

/** Email used for the backend X-Demo-User header. */
export async function sessionEmail(): Promise<string | null> {
  return (await getSession())?.email ?? null;
}
