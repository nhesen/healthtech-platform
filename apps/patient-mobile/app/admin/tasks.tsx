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
import { api, patch, post } from "@/services/api";
import type { HospitalTask } from "@/types/api";

/** A task leaves the queue once completed, so the discharge and cleaning steps are tracked separately. */
interface Followup { id: string; title: string; patient_id: string; admission_id: string; stage: "READY" | "BLOCKED" | "DISCHARGED" | "CLEAN"; bed?: string }

export default function Tasks() {
  const state = useApi(() => api<HospitalTask[]>("/tasks"), [], 5000);
  const [followups, setFollowups] = useState<Followup[]>([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  function track(next: Followup) { setFollowups(prev => [next, ...prev.filter(item => item.id !== next.id)]); }
  async function guard(key: string, action: () => Promise<void>) {
    setBusy(key); setError("");
    try { await action(); } catch (value) { setError(value instanceof Error ? value.message : "The action could not be completed."); } finally { setBusy(""); }
  }
  const start = (task: HospitalTask) => guard(task.id, async () => { await patch(`/tasks/${task.id}`, { status: "IN_PROGRESS" }); await state.reload(); });
  const complete = (task: HospitalTask) => guard(task.id, async () => {
    const result = await post<{ task_status: string; admission_status: string }>(`/tasks/${task.id}/complete`);
    track({ id: task.id, title: task.title, patient_id: task.patient_id, admission_id: task.admission_id, stage: result.admission_status === "READY_FOR_DISCHARGE" ? "READY" : "BLOCKED" });
    await state.reload();
  });
  const discharge = (item: Followup) => guard(item.id, async () => {
    const result = await post<{ status: string; bed_id: string; bed_status: string }>(`/admissions/${item.admission_id}/discharge`);
    track({ ...item, stage: "DISCHARGED", bed: result.bed_id });
    await state.reload();
  });
  const clean = (item: Followup) => guard(item.id, async () => {
    if (!item.bed) return;
    await post<{ bed_id: string; status: string }>(`/beds/${item.bed}/complete-cleaning`);
    track({ ...item, stage: "CLEAN" });
    await state.reload();
  });

  if (state.loading && !state.data) return <Screen><LoadingState label="Loading the task queue…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Discharge tasks" subtitle="Ordered by priority score"/>
    {error ? <Text style={styles.error}>{error}</Text> : null}

    {followups.length ? <>
      <Text style={styles.section}>Follow-up</Text>
      {followups.map(item => <Card key={`f-${item.id}`} title={item.title}>
        <Pill label={item.stage} tone={item.stage === "CLEAN" ? "green" : item.stage === "BLOCKED" ? "red" : "amber"}/>
        <Text style={styles.body}>{item.stage === "READY" ? "Blockers cleared. The patient can be discharged." : item.stage === "BLOCKED" ? "Other blockers are still open on this admission." : item.stage === "DISCHARGED" ? `Bed ${item.bed} is being cleaned.` : "Bed returned to the available pool."}</Text>
        {item.stage === "READY" ? <AppButton label="Discharge patient" loading={busy === item.id} disabled={Boolean(busy)} onPress={() => discharge(item)}/> : null}
        {item.stage === "DISCHARGED" ? <AppButton label="Complete bed cleaning" loading={busy === item.id} disabled={Boolean(busy)} onPress={() => clean(item)}/> : null}
      </Card>)}
    </> : null}

    <Text style={styles.section}>Queue</Text>
    {state.data.length ? state.data.map(task => <Card key={task.id} title={task.title}>
      <View style={styles.row}><Pill label={task.priority} tone={["HIGH", "CRITICAL"].includes(task.priority) ? "red" : task.priority === "MEDIUM" ? "amber" : "gray"}/><Pill label={task.status} tone={task.status === "IN_PROGRESS" ? "amber" : "blue"}/><Text style={styles.score}>{task.priority_score}</Text></View>
      <Detail label="Patient" value={task.patient_id}/>
      <Detail label="Blocker" value={task.blocker_type.replaceAll("_", " ")}/>
      <Detail label="Owner" value={task.assigned_role}/>
      <Detail label="Impact" value={task.impact}/>
      {task.status === "PENDING" ? <AppButton label="Start task" loading={busy === task.id} disabled={Boolean(busy)} onPress={() => start(task)}/> : null}
      {task.status === "IN_PROGRESS" ? <AppButton label="Complete task" loading={busy === task.id} disabled={Boolean(busy)} onPress={() => complete(task)}/> : null}
    </Card>) : <EmptyState title="No open tasks" message="Every discharge blocker is resolved."/>}
  </Screen>;
}
function Detail({ label, value }: { label: string; value: string }) { return <View style={styles.detail}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value || "—"}</Text></View>; }
const styles = StyleSheet.create({
  section: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: spacing.sm },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginBottom: spacing.sm },
  score: { marginLeft: "auto", color: colors.primary, fontWeight: "900" },
  detail: { flexDirection: "row", justifyContent: "space-between", gap: 16, paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  label: { color: colors.secondary, fontSize: 13 }, value: { color: colors.text, fontWeight: "700", flex: 1, textAlign: "right", fontSize: 13 },
  body: { color: colors.secondary, lineHeight: 21, marginVertical: spacing.md }, error: { color: colors.danger, lineHeight: 20 },
});
