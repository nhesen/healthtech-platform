import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api } from "@/services/api";
import type { CapacityForecast, Recommendation } from "@/types/api";

export default function Analytics() {
  const state = useApi(async () => {
    const [forecast, recommendations] = await Promise.all([api<CapacityForecast>(`/hospitals/${HOSPITAL_ID}/forecast`), api<Recommendation[]>(`/hospitals/${HOSPITAL_ID}/recommendations`)]);
    return { forecast, recommendations };
  }, [], 10000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading the capacity forecast…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const { forecast, recommendations } = state.data;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Analytics" subtitle="Forecast and recommended actions"/>
    <Card eyebrow="FORECAST" title={forecast.predicted_shortage > 0 ? `Shortage of ${forecast.predicted_shortage} beds` : `${forecast.future_capacity} beds spare`}>
      <Row label="Available now" value={forecast.available_now}/>
      <Row label="Usable discharges" value={forecast.expected_usable_discharges}/>
      <Row label="Expected incoming" value={forecast.expected_incoming}/>
      <Row label="Future capacity" value={forecast.future_capacity} tone={forecast.future_capacity < 0 ? colors.danger : colors.success}/>
      <Text style={styles.footnote}>{forecast.method}</Text>
    </Card>
    <Text style={styles.section}>Recommendations</Text>
    {recommendations.length ? recommendations.map(item => <Card key={item.task_id} title={item.action}>
      <Pill label={item.priority} tone={["HIGH", "CRITICAL"].includes(item.priority) ? "red" : item.priority === "MEDIUM" ? "amber" : "gray"}/>
      <Row label="Problem" text={item.problem.replaceAll("_", " ")}/>
      <Row label="Patient" text={item.patient}/>
      <Row label="Impact" text={item.impact}/>
      <Text style={styles.footnote}>{item.why}</Text>
    </Card>) : <EmptyState title="Nothing to recommend" message="No discharge blocker is holding a bed right now."/>}
  </Screen>;
}
function Row({ label, value, text, tone }: { label: string; value?: number; text?: string; tone?: string }) {
  return <View style={styles.row}><Text style={styles.label}>{label}</Text><Text style={[styles.value, tone ? { color: tone } : null]}>{value ?? text ?? "—"}</Text></View>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", justifyContent: "space-between", gap: 16, paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  label: { color: colors.secondary, fontSize: 13 }, value: { color: colors.text, fontWeight: "700", flex: 1, textAlign: "right", fontSize: 13 },
  footnote: { color: colors.secondary, fontSize: 12, lineHeight: 18, marginTop: spacing.md },
  section: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: spacing.sm },
});
