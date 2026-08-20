import { useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api, post } from "@/services/api";
import { getSession } from "@/services/session";

const REASONS = ["Patient unconscious", "Emergency treatment required", "Critical medical situation"] as const;

export default function Emergency() {
  const [patientId, setPatientId] = useState(PATIENT_ID);
  const [reason, setReason] = useState<typeof REASONS[number]>("Patient unconscious");
  const [confirm, setConfirm] = useState(false);
  const [notice, setNotice] = useState("");
  const session = useApi(() => getSession(), []);
  const state = useApi(() => api<any>(`/emergency/summary/${patientId}`), [patientId]);

  async function glass() {
    try {
      await post("/emergency/break-glass", { patient_id: patientId, reason });
      setConfirm(false);
      setNotice("Temporary emergency access is open for 5 minutes. The action is audited.");
      await state.reload();
    } catch (value) { setNotice(value instanceof Error ? value.message : "Break-glass could not be opened."); }
  }

  const clinician = session.data && session.data.role !== "PATIENT";
  if (state.loading && !state.data && !state.error) return <Screen><LoadingState label="Opening emergency snapshot…"/></Screen>;
  const summary = state.data;

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Emergency snapshot" subtitle="Critical details only" back/>
    {clinician ? <Card title="Patient ID">
      <TextInput value={patientId} onChangeText={setPatientId} style={styles.input} accessibilityLabel="Patient ID"/>
      <AppButton label="Open if authorised" variant="secondary" onPress={() => void state.reload()}/>
      <Text style={styles.warn}>Emergency access will temporarily expose critical patient information. Reason is required. This action will be logged and audited.</Text>
      {REASONS.map(item => <AppButton key={item} label={item} variant={reason === item ? "primary" : "secondary"} onPress={() => setReason(item)}/>)}
      {confirm ? <AppButton label="Confirm emergency access" onPress={() => void glass()}/> : <AppButton label="Break-glass access" variant="danger" onPress={() => setConfirm(true)}/>}
    </Card> : null}
    {notice ? <Text style={styles.warn}>{notice}</Text> : null}
    {state.error && !summary ? <ErrorState message={state.error} retry={state.reload}/> : null}
    {summary ? <Card title={summary.patient.name}>
      <Pill label={summary.access} tone={summary.access === "BREAK_GLASS" ? "amber" : "blue"}/>
      <Text style={styles.meta}>{summary.patient.id} · Blood group {summary.patient.blood_type}</Text>
      <Text style={styles.label}>Allergies</Text>
      <Text style={styles.body}>{(summary.allergies || []).map((x: any) => x.name || x).join(", ") || "None recorded"}</Text>
      <Text style={styles.label}>Medications</Text>
      {(summary.medications || []).map((item: any, index: number) => <Text key={index} style={styles.body}>{item.name} {item.dosage}</Text>)}
      <Text style={styles.label}>Chronic conditions</Text>
      <Text style={styles.body}>{(summary.chronic_conditions || []).join(", ") || "None recorded"}</Text>
      {(summary.critical_warnings || []).map((item: any, index: number) => <View key={index} style={styles.warnBox}><Text style={styles.warn}>{item.severity} · {item.detail}</Text></View>)}
      <Text style={styles.meta}>{summary.disclaimer}</Text>
    </Card> : null}
  </Screen>;
}
const styles = StyleSheet.create({
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, padding: spacing.md, marginBottom: spacing.md, color: colors.text },
  warn: { color: "#B45309", lineHeight: 20, marginVertical: spacing.sm },
  meta: { color: colors.secondary, fontSize: 12, marginTop: spacing.sm },
  label: { color: colors.text, fontWeight: "800", marginTop: spacing.md },
  body: { color: colors.secondary, lineHeight: 20 },
  warnBox: { backgroundColor: "#FEF2F2", borderRadius: 12, padding: spacing.md, marginTop: spacing.sm },
});
