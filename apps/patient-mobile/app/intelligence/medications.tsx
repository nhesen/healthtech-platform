import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api } from "@/services/api";

interface Alert {
  id: string; patient_id: string; patient_name: string; alert_type: string; severity: string; status: string;
  medication_a: string; medication_b?: string; explanation: string; recommended_action: string; created_at: string; disclaimer: string;
}

export default function MedicationSafety() {
  const state = useApi(() => api<Alert[]>("/medication-alerts"), [], 15000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading medication safety…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Medication safety" subtitle="Decision support for clinician review" back/>
    {state.data.length ? state.data.map(item => <Card key={item.id} title={`${item.medication_a}${item.medication_b ? ` + ${item.medication_b}` : ""}`}>
      <View style={styles.row}><Pill label={item.severity} tone={item.severity === "CRITICAL" || item.severity === "HIGH" ? "red" : item.severity === "MEDIUM" ? "amber" : "green"}/><Pill label={item.status} tone="gray"/></View>
      <Text style={styles.body}>{item.explanation}</Text>
      <Text style={styles.action}>{item.recommended_action}</Text>
      <Text style={styles.foot}>{item.patient_name} · {item.alert_type.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleString()}</Text>
      <Text style={styles.foot}>{item.disclaimer}</Text>
    </Card>) : <EmptyState title="No medication alerts"/>}
  </Screen>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.sm },
  body: { color: colors.secondary, lineHeight: 21 }, action: { color: colors.text, fontWeight: "700", marginTop: spacing.sm },
  foot: { color: colors.secondary, fontSize: 12, marginTop: spacing.sm },
});
