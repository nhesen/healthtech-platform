import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

const KEY = "healthtech.patient.session";
const DEMO_EMAIL = "patient@demo.az";

async function setValue(value: string | null) {
  if (Platform.OS === "web") {
    if (value) localStorage.setItem(KEY, value); else localStorage.removeItem(KEY);
    return;
  }
  if (value) await SecureStore.setItemAsync(KEY, value); else await SecureStore.deleteItemAsync(KEY);
}

export async function getSession() {
  if (Platform.OS === "web") return localStorage.getItem(KEY);
  return SecureStore.getItemAsync(KEY);
}
export async function startDemoSession() { await setValue(DEMO_EMAIL); return DEMO_EMAIL; }
export async function clearSession() { await setValue(null); }
