import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { ListRow } from "@/components/ListRow";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api, post } from "@/services/api";
import type { HospitalCapacity, HospitalTask, SafetyEvent } from "@/types/api";

export default function CommandCenter() {
  const state = useApi(async () => {
    const [capacity, tasks, safety] = await Promise.all([api<HospitalCapacity>(`/hospitals/${HOSPITAL_ID}/capacity`), api<HospitalTask[]>("/tasks"), api<SafetyEvent[]>("/safety/events")]);
    return { capacity, tasks, safety };
  }, [], 5000);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function run(kind: "simulate" | "reset") {
    setBusy(kind); setNotice("");
    try {
      if (kind === "simulate") { await post("/cv-events", { hospital_id: HOSPITAL_ID, room_id: "204", event_type: "FALL_RISK", severity: "HIGH", confidence: 0.91, patient_state: "STANDING", previous_state: "SITTING", metadata: { source: "mobile_command_center", demo: true } }); setNotice("Fall-risk event sent for room 204."); }
      else { await post("/demo/reset"); setNotice("Demo data restored."); }
      await state.reload();
    } catch (value) { setNotice(value instanceof Error ? value.message : "The action could not be completed."); }
    finally { setBusy(""); }
  }

  if (state.loading && !state.data) return <Screen><LoadingState label="Loading hospital capacity…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const { capacity, tasks, safety } = state.data;
  const active = safety.find(item => item.status !== "RESOLVED");
  const critical = tasks.filter(item => ["HIGH", "CRITICAL"].includes(item.priority)).length;

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Command centre" subtitle="Refreshes every 5 seconds"/>
    <View style={styles.grid}>
      <Stat label="Available" value={capacity.available} tone={capacity.available < 10 ? colors.danger : colors.success}/>
      <Stat label="Occupied" value={capacity.occupied}/>
      <Stat label="Cleaning" value={capacity.cleaning} tone={colors.warning}/>
      <Stat label="Total beds" value={capacity.total_beds}/>
      <Stat label="Emergency waiting" value={capacity.emergency_waiting} tone={capacity.emergency_waiting > 0 ? colors.warning : undefined}/>
      <Stat label="Expected incoming" value={capacity.expected_incoming}/>
      <Stat label="Expected discharges" value={capacity.expected_discharges}/>
      <Stat label="Delayed discharges" value={capacity.delayed_discharges} tone={capacity.delayed_discharges > 0 ? colors.danger : undefined}/>
    </View>

    <Card eyebrow="PATIENT SAFETY" title={active ? `Room ${active.room_id}` : "No active event"}>
      {active ? <>
        <View style={styles.row}><Pill label={active.status ?? "ACTIVE"} tone={active.status === "ACKNOWLEDGED" ? "amber" : "red"}/><Text style={styles.meta}>{Math.round(active.confidence * 100)}% confidence</Text></View>
        <Text style={styles.body}>{(active.previous_state ?? "UNKNOWN").toLowerCase()} → {(active.patient_state ?? "UNKNOWN").toLowerCase()} · {new Date(active.occurred_at).toLocaleTimeString()}</Text>
        <AppButton label="Open safety board" variant="secondary" onPress={() => router.push("/admin/safety")}/>
      </> : <Text style={styles.body}>Camera monitoring is idle. Simulate an event to walk through the escalation flow.</Text>}
    </Card>

    <Card eyebrow="DISCHARGE" title={`${tasks.length} open tasks`}>
      <Text style={styles.body}>{critical} high priority · {capacity.delayed_discharges} blocked discharges</Text>
      <AppButton label="Open task queue" variant="secondary" onPress={() => router.push("/admin/tasks")}/>
    </Card>

    <Card title="Hospital views">
      <ListRow icon="office-building-outline" title="Departments" subtitle="Beds per department" onPress={() => router.push("/hospital/departments")}/>
      <ListRow icon="bed-outline" title="Beds" subtitle="Status and occupancy" onPress={() => router.push("/hospital/beds")}/>
      <ListRow icon="swap-horizontal" title="Patient flow" subtitle="Admission stages" onPress={() => router.push("/hospital/flow")}/>
      <ListRow icon="history" title="Audit trail" subtitle="Operational events" onPress={() => router.push("/hospital/audit")}/>
    </Card>

    <Card title="Demo controls">
      <View style={styles.actions}>
        <AppButton label="Simulate fall risk" variant="secondary" loading={busy === "simulate"} disabled={Boolean(busy)} onPress={() => run("simulate")}/>
        <AppButton label="Reset demo data" variant="danger" loading={busy === "reset"} disabled={Boolean(busy)} onPress={() => run("reset")}/>
      </View>
      {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    </Card>
  </Screen>;
}
function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return <Card style={styles.stat}><Text style={styles.label}>{label}</Text><Text style={[styles.value, tone ? { color: tone } : null]}>{value}</Text></Card>;
}
const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  stat: { width: "48%", padding: spacing.md }, label: { color: colors.secondary, fontSize: 11, fontWeight: "700" },
  value: { color: colors.primary, fontSize: 26, fontWeight: "900", marginTop: 4 },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  meta: { color: colors.secondary, fontSize: 12 }, body: { color: colors.secondary, lineHeight: 21, marginVertical: spacing.md },
  actions: { gap: spacing.sm }, notice: { color: colors.primaryDark, fontSize: 13, lineHeight: 19, marginTop: spacing.md },
});
