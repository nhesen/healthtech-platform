import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { LabResult, TrendsResponse } from "@/types/api";

export default function Labs() {
  const state = useApi(async () => { const [trends, labs] = await Promise.all([api<TrendsResponse>(`/patients/${PATIENT_ID}/trends`), api<LabResult[]>(`/patients/${PATIENT_ID}/lab-results`)]); return { trends, labs }; }, []);
  if (state.loading && !state.data) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  return <Screen><PageHeader title="Lab Results" subtitle="Tap a result for its history" back/>{!state.data.trends.trends.length ? <EmptyState/> : state.data.trends.trends.map(trend => { const latest = state.data!.labs.find(item => item.metric === trend.metric); return <Pressable key={trend.metric} onPress={() => router.push({ pathname: "/health/lab/[id]", params: { id: trend.metric } })} style={({ pressed }) => [styles.card, pressed && { opacity: .7 }]}><View style={styles.top}><View><Text style={styles.name}>{trend.metric}</Text><Text style={styles.reference}>Reference: {latest?.reference_range || "Not supplied"}</Text></View><Pill label={trend.trend} tone={trend.trend === "increasing" ? "amber" : trend.trend === "stable" ? "green" : "blue"}/></View><View style={styles.metric}><Text style={styles.value}>{trend.current}</Text><Text style={styles.unit}>{latest?.unit}</Text></View><Text style={[styles.change, { color: trend.change > 0 ? colors.warning : colors.success }]}>{trend.change > 0 ? "+" : ""}{trend.change} since previous</Text></Pressable>; })}</Screen>;
}
const styles = StyleSheet.create({ card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg }, top: { flexDirection: "row", justifyContent: "space-between", gap: 10 }, name: { color: colors.text, fontSize: 18, fontWeight: "900" }, reference: { color: colors.secondary, fontSize: 12, marginTop: 4 }, metric: { flexDirection: "row", alignItems: "baseline", marginTop: spacing.lg }, value: { color: colors.text, fontSize: 36, fontWeight: "900" }, unit: { color: colors.secondary, fontSize: 16, marginLeft: 4 }, change: { marginTop: 3, fontWeight: "700" } });
