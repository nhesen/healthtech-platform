import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { RoleGate } from "@/components/RoleGate";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api, patch, post } from "@/services/api";
import type { Consultation, DoctorAppointment, PatientBrief, TimelineRecord } from "@/types/api";

const STAGES = ["SCHEDULED", "CHECKED_IN", "WAITING", "IN_PROGRESS"];
const DEMO_NOTES = "Patient reports increased thirst and fatigue over three weeks. Reviewed rising HbA1c trend and current metformin dose.";

export default function ConsultationRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <RoleGate role="DOCTOR"><Workspace id={String(id)}/></RoleGate>;
}

function Workspace({ id }: { id: string }) {
  const state = useApi(async () => {
    const appointments = await api<DoctorAppointment[]>("/appointments");
    const appointment = appointments.find(item => item.id === id) ?? null;
    if (!appointment) return { appointment, brief: null, timeline: [] as TimelineRecord[], blocked: "" };
    let brief: PatientBrief | null = null, timeline: TimelineRecord[] = [], blocked = "";
    try { brief = await api<PatientBrief>(`/doctors/patients/${appointment.patient_id}/brief`); }
    catch (value) { blocked = value instanceof Error ? value.message : "This record is not available."; }
    try { timeline = await api<TimelineRecord[]>(`/patients/${appointment.patient_id}/timeline`); } catch { /* consent scoped, brief already reports why */ }
    return { appointment, brief, timeline, blocked };
  }, [id]);
  const [notes, setNotes] = useState("");
  const [draft, setDraft] = useState<Consultation>();
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  async function generate() {
    setBusy("draft"); setError("");
    try { setDraft(await post<Consultation>("/consultations", { appointment_id: id, doctor_notes: notes, complete: false })); }
    catch (value) { setError(value instanceof Error ? value.message : "The draft could not be generated."); }
    finally { setBusy(""); }
  }
  async function complete() {
    const appointment = state.data?.appointment; if (!appointment) return;
    setBusy("complete"); setError("");
    try {
      for (let index = STAGES.indexOf(appointment.status) + 1; index < STAGES.length; index++) await patch(`/appointments/${appointment.id}/status`, { status: STAGES[index] });
      setDraft(await post<Consultation>("/consultations", { appointment_id: id, doctor_notes: notes, final_note: notes, complete: true }));
      await state.reload();
    } catch (value) { setError(value instanceof Error ? value.message : "The consultation could not be completed."); }
    finally { setBusy(""); }
  }

  if (state.loading && !state.data) return <Screen><LoadingState label="Opening the patient record…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const { appointment, brief, timeline, blocked } = state.data;
  if (!appointment) return <Screen><PageHeader title="Consultation" back/><EmptyState title="Appointment not found" message="It may have been cancelled or reassigned."/></Screen>;
  const ready = STAGES.includes(appointment.status) && notes.trim().length > 0;

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title={appointment.patient_name} subtitle={appointment.reason || "Consultation"} back/>
    <Card>
      <View style={styles.row}><Pill label={appointment.status} tone={appointment.status === "COMPLETED" ? "green" : appointment.status === "WAITING" ? "amber" : "blue"}/><Text style={styles.time}>{new Date(appointment.starts_at).toLocaleString()}</Text></View>
    </Card>

    {blocked ? <Card eyebrow="ACCESS" title="Record is closed"><Text style={styles.body}>{blocked}</Text><Text style={styles.footnote}>The citizen grants access per category from the app. Without an active consent the record stays closed.</Text></Card> : null}

    {brief ? <>
      <Card eyebrow="BRIEF" title="Summary">
        {brief.summary ? <Text style={styles.body}>{brief.summary}</Text> : null}
        <Text style={styles.footnote}>Consent covers: {brief.allowed_categories.map(x => x.replaceAll("_", " ").toLowerCase()).join(", ")}</Text>
      </Card>
      {brief.warnings.length || brief.ai_warnings.length ? <Card eyebrow="REQUIRES REVIEW" title="Conflicts">
        {brief.warnings.map((item, index) => <Text key={`w${index}`} style={styles.warning}>{item.message}</Text>)}
        {brief.ai_warnings.map((item, index) => <Text key={`a${index}`} style={styles.warning}>{item}</Text>)}
      </Card> : null}
      {brief.relevant_metrics.length ? <Card title="Metrics">{brief.relevant_metrics.map(item => <View key={item.metric} style={styles.metric}><Text style={styles.metricName}>{item.metric}</Text><Text style={styles.metricValue}>{item.current}{item.previous !== null ? <Text style={styles.metricChange}>  {item.change > 0 ? "↑" : item.change < 0 ? "↓" : "→"} {item.change}</Text> : null}</Text></View>)}</Card> : null}
      {brief.medications.length ? <Card title="Medications">{brief.medications.map((item, index) => <Text key={`m${index}`} style={styles.listItem}>{item.name}{item.dosage ? ` · ${item.dosage}` : ""}</Text>)}</Card> : null}
      {brief.allergies.length ? <Card title="Allergies">{brief.allergies.map((item, index) => <Text key={`al${index}`} style={styles.listItem}>{item.name}{item.reaction ? ` · ${item.reaction}` : ""}</Text>)}</Card> : null}
      {brief.important_history.length ? <Card title="History">{brief.important_history.map((item, index) => <Text key={`h${index}`} style={styles.listItem}>{item}</Text>)}</Card> : null}
    </> : null}

    {timeline.length ? <Card title="Timeline">{timeline.slice(0, 8).map((item, index) => <View key={item.id ?? index} style={styles.timelineItem}><Text style={styles.listItem}>{item.title}</Text><Text style={styles.footnote}>{item.record_date} · {item.type.replaceAll("_", " ")}</Text></View>)}</Card> : null}

    <Card title="Consultation notes">
      <TextInput value={notes} onChangeText={setNotes} multiline placeholder="Record what you observed and discussed." placeholderTextColor={colors.secondary} style={styles.input} accessibilityLabel="Consultation notes"/>
      <View style={styles.actions}>
        <AppButton label="Load demo notes" variant="secondary" onPress={() => setNotes(DEMO_NOTES)}/>
        <AppButton label="Generate AI draft" loading={busy === "draft"} disabled={!notes.trim() || Boolean(busy)} onPress={generate}/>
      </View>
    </Card>

    {draft ? <Card eyebrow={`DRAFT · ${draft.status}`} title="AI assessment draft">
      <Text style={styles.body}>{draft.ai_draft.assessment_draft ?? "No draft text was returned."}</Text>
      {draft.missing_information.length ? <View style={styles.missing}><Text style={styles.missingTitle}>Missing information</Text>{draft.missing_information.map((item, index) => <Text key={index} style={styles.footnote}>· {item.message}</Text>)}</View> : null}
      <Text style={styles.footnote}>Decision support only. The clinician approves the final note.</Text>
    </Card> : null}

    {error ? <Text style={styles.error}>{error}</Text> : null}
    <AppButton label="Approve and complete" loading={busy === "complete"} disabled={!ready || Boolean(busy)} onPress={complete}/>
    {appointment.status === "COMPLETED" ? <Text style={styles.footnote}>This consultation is already completed.</Text> : null}
  </Screen>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  time: { color: colors.secondary, fontSize: 13 }, body: { color: colors.secondary, lineHeight: 21 },
  footnote: { color: colors.secondary, fontSize: 12, lineHeight: 18, marginTop: spacing.sm },
  warning: { color: "#B45309", lineHeight: 20, marginBottom: spacing.sm, fontWeight: "700" },
  metric: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  metricName: { color: colors.secondary }, metricValue: { color: colors.text, fontWeight: "800" }, metricChange: { color: colors.warning, fontWeight: "700" },
  listItem: { color: colors.text, fontWeight: "700", lineHeight: 21 }, timelineItem: { paddingVertical: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  input: { minHeight: 108, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: spacing.md, color: colors.text, textAlignVertical: "top", lineHeight: 20 },
  actions: { gap: spacing.sm, marginTop: spacing.md },
  missing: { backgroundColor: colors.muted, borderRadius: radius.sm, padding: spacing.md, marginTop: spacing.md },
  missingTitle: { color: colors.text, fontWeight: "800", fontSize: 13 }, error: { color: colors.danger, lineHeight: 20 },
});
