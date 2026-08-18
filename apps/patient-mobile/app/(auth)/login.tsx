import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppButton } from "@/components/AppButton";
import { colors, radius, spacing } from "@/constants/theme";
import { API_URL, DEMO_MODE, api } from "@/services/api";
import { getSession, startDemoSession } from "@/services/session";
import type { DemoUser } from "@/types/api";

export default function Login() {
  const [loading, setLoading] = useState(false); const [error, setError] = useState("");
  useEffect(() => { void getSession().then(value => { if (value) router.replace("/(tabs)"); }); }, []);
  async function continueDemo() {
    setLoading(true); setError("");
    try { await api<DemoUser>("/auth/me"); await startDemoSession(); router.replace("/(tabs)"); }
    catch (value) { setError(value instanceof Error ? value.message : "The demo backend is unavailable."); }
    finally { setLoading(false); }
  }
  return <SafeAreaView style={styles.safe}><View style={styles.content}><View style={styles.brand}><View style={styles.logo}><MaterialCommunityIcons name="heart-pulse" size={38} color="white"/></View><Text style={styles.name}>HealthTech</Text><Text style={styles.tagline}>Your health journey, connected.</Text></View><View style={styles.panel}><View style={styles.demo}><Text style={styles.demoText}>DEMO MODE</Text></View><Text style={styles.title}>Welcome, Hasan</Text><Text style={styles.body}>Access your synthetic health timeline, doctors, appointments, documents, and permissions.</Text>{error ? <Text style={styles.error}>{error}</Text> : null}<AppButton label="Continue as Patient" loading={loading} disabled={!DEMO_MODE || !API_URL} onPress={continueDemo}/>{!API_URL ? <Text style={styles.hint}>Set EXPO_PUBLIC_API_URL to the deployed HTTPS API or this computer&apos;s LAN backend address.</Text> : null}</View><Text style={styles.disclaimer}>Synthetic hackathon data only · Decision support, not medical advice</Text></View></SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { flex: 1, justifyContent: "space-between", padding: spacing.xl }, brand: { alignItems: "center", marginTop: 54 }, logo: { width: 76, height: 76, borderRadius: 24, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center", shadowColor: colors.primary, shadowOpacity: .2, shadowRadius: 16, elevation: 4 }, name: { marginTop: 18, color: colors.text, fontSize: 30, fontWeight: "900" }, tagline: { color: colors.secondary, marginTop: 5, fontSize: 15 }, panel: { borderRadius: radius.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.lg }, demo: { alignSelf: "flex-start", backgroundColor: colors.primaryLight, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 99 }, demoText: { color: colors.primaryDark, fontSize: 11, fontWeight: "900", letterSpacing: 1 }, title: { color: colors.text, fontSize: 24, fontWeight: "900" }, body: { color: colors.secondary, lineHeight: 22 }, error: { color: colors.danger, lineHeight: 20 }, hint: { color: colors.warning, fontSize: 12, lineHeight: 18 }, disclaimer: { color: colors.secondary, textAlign: "center", fontSize: 11, lineHeight: 17 } });
