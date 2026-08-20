import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api, patch, post } from "@/services/api";
import type { SafetyEvent } from "@/types/api";

export default function Safety() {
  const state = useApi(() => api<SafetyEvent[]>("/safety/events"), [], 5000);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function guard(key: string, action: () => Promise<void>) {
    setBusy(key); setError("");
    try { await action(); await state.reload(); } catch (value) { setError(value instanceof Error ? value.message : "The action could not be completed."); } finally { setBusy(""); }
  }
  const simulate = () => guard("simulate", () => post("/cv-events", { hospital_id: HOSPITAL_ID, room_id: "204", event_type: "FALL_RISK", severity: "HIGH", confidence: 0.91, patient_state: "STANDING", previous_state: "SITTING", metadata: { source: "mobile_safety_board", demo: true } }));

  if (state.loading && !state.data) return <Screen><LoadingState label="Loading the safety board…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const active = state.data.find(item => item.status !== "RESOLVED");
  const history = state.data.filter(item => item.id !== active?.id);

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Patient safety" subtitle="Camera events and nurse dispatch"/>
    {error ? <Text style={styles.error}>{error}</Text> : null}

    {active ? <Card eyebrow={`ROOM ${active.room_id}`} title={active.event_type.replaceAll("_", " ")}>
      <View style={styles.row}><Pill label={active.status ?? "ACTIVE"} tone={active.status === "ACKNOWLEDGED" ? "amber" : "red"}/><Pill label={active.severity} tone="red"/><Text style={styles.meta}>{Math.round(active.confidence * 100)}%</Text></View>
      <Text style={styles.body}>{(active.previous_state ?? "unknown").toLowerCase()} → {(active.patient_state ?? "unknown").toLowerCase()}</Text>
      <Text style={styles.footnote}>Detected {new Date(active.occurred_at).toLocaleString()}</Text>
      <View style={styles.actions}>
        {active.status === "ACTIVE" ? <AppButton label="Acknowledge" loading={busy === "ack"} disabled={Boolean(busy)} onPress={() => guard("ack", () => patch(`/cv-events/${active.id}/acknowledge`))}/> : null}
        <AppButton label="Send nurse" variant="secondary" loading={busy === "nurse"} disabled={Boolean(busy)} onPress={() => guard("nurse", () => post(`/cv-events/${active.id}/send-nurse`))}/>
        {active.status === "ACKNOWLEDGED" ? <AppButton label="Resolve event" variant="secondary" loading={busy === "resolve"} disabled={Boolean(busy)} onPress={() => guard("resolve", () => patch(`/cv-events/${active.id}/resolve`))}/> : null}
      </View>
      {active.nurse_tasks.length ? <View style={styles.tasks}><Text style={styles.tasksTitle}>Nurse tasks</Text>{active.nurse_tasks.map(task => <View key={task.id} style={styles.task}><Text style={styles.taskTitle}>{task.title}</Text><Text style={styles.footnote}>{task.assigned_role} · {task.priority} · {task.status}</Text></View>)}</View> : null}
    </Card> : <Card title="No active event">
      <Text style={styles.body}>Camera monitoring is idle. Simulate a fall-risk event to walk through acknowledge, dispatch, and resolve.</Text>
      <AppButton label="Simulate fall risk" loading={busy === "simulate"} disabled={Boolean(busy)} onPress={simulate}/>
    </Card>}

    <Text style={styles.section}>History</Text>
    {history.length ? history.slice(0, 20).map(item => <Card key={item.id}>
      <View style={styles.row}><Pill label={item.status ?? "LOGGED"} tone={item.status === "RESOLVED" ? "green" : item.status === "ACKNOWLEDGED" ? "amber" : "red"}/><Text style={styles.meta}>Room {item.room_id}</Text></View>
      <Text style={styles.historyLine}>{item.event_type.replaceAll("_", " ")} · {Math.round(item.confidence * 100)}%</Text>
      <Text style={styles.footnote}>{new Date(item.occurred_at).toLocaleString()}{item.resolved_at ? ` · resolved ${new Date(item.resolved_at).toLocaleTimeString()}` : ""}</Text>
    </Card>) : <EmptyState title="No earlier events"/>}
  </Screen>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  meta: { color: colors.secondary, fontSize: 12, marginLeft: "auto" },
  body: { color: colors.secondary, lineHeight: 21, marginTop: spacing.md },
  footnote: { color: colors.secondary, fontSize: 12, lineHeight: 18, marginTop: spacing.xs },
  actions: { gap: spacing.sm, marginTop: spacing.lg },
  tasks: { marginTop: spacing.lg, backgroundColor: colors.muted, borderRadius: 12, padding: spacing.md },
  tasksTitle: { color: colors.text, fontWeight: "800", fontSize: 13, marginBottom: spacing.sm },
  task: { paddingVertical: spacing.xs }, taskTitle: { color: colors.text, fontWeight: "700" },
  section: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: spacing.sm },
  historyLine: { color: colors.text, fontWeight: "700", marginTop: spacing.sm },
  error: { color: colors.danger, lineHeight: 20 },
});
