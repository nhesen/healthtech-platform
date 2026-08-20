import { router } from "expo-router";
import type { Href } from "expo-router";
import { useMemo, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api, post } from "@/services/api";
import type { DoctorAppointment, Notification, QueueAdvance } from "@/types/api";

const OPEN = ["SCHEDULED", "CHECKED_IN", "WAITING", "IN_PROGRESS"];
function tone(status: string) { return status === "COMPLETED" ? "green" : status === "CANCELLED" ? "gray" : status === "WAITING" ? "amber" : "blue"; }

export default function DoctorPatients() {
  const state = useApi(async () => {
    const [appointments, notifications] = await Promise.all([api<DoctorAppointment[]>("/appointments"), api<Notification[]>("/notifications")]);
    return { appointments, notifications };
  }, [], 10000);
  const [advancing, setAdvancing] = useState(false);
  const [notice, setNotice] = useState("");
  const queue = useMemo(() => [...(state.data?.appointments ?? [])].sort((a, b) => a.starts_at.localeCompare(b.starts_at)), [state.data]);

  async function advance() {
    setAdvancing(true); setNotice("");
    try { const result = await post<QueueAdvance>("/demo/queue/advance"); setNotice(`Queue advanced · ${result.patients_before} patients before, about ${result.estimated_wait_minutes} min`); await state.reload(); }
    catch (value) { setNotice(value instanceof Error ? value.message : "The demo queue could not be advanced."); }
    finally { setAdvancing(false); }
  }

  if (state.loading && !state.data) return <Screen><LoadingState label="Loading your clinic list…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const unread = state.data.notifications.filter(x => !x.read_at).length;
  const waiting = queue.filter(x => x.status === "WAITING").length;
  const open = queue.filter(x => OPEN.includes(x.status));

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Clinic list" subtitle="Refreshes every 10 seconds" action={{ icon: "bell-outline", badge: unread, onPress: () => router.push("/doctor/alerts") }}/>
    <View style={styles.statGrid}>
      <Card style={styles.stat}><Text style={styles.label}>Scheduled</Text><Text style={styles.big}>{open.length}</Text></Card>
      <Card style={styles.stat}><Text style={styles.label}>Waiting</Text><Text style={[styles.big, waiting > 0 && { color: colors.warning }]}>{waiting}</Text></Card>
      <Card style={styles.stat}><Text style={styles.label}>Alerts</Text><Text style={[styles.big, unread > 0 && { color: colors.danger }]}>{unread}</Text></Card>
    </View>
    <AppButton label="Advance demo queue" variant="secondary" loading={advancing} onPress={advance}/>
    <AppButton label="Medication safety" variant="secondary" onPress={() => router.push("/intelligence/medications")}/>
    <AppButton label="Emergency snapshot" variant="secondary" onPress={() => router.push("/emergency" as Href)}/>
    {notice ? <Text style={styles.notice}>{notice}</Text> : null}
    <Text style={styles.section}>Today</Text>
    {queue.length ? queue.map(item => <Pressable key={item.id} onPress={() => router.push({ pathname: "/consultation/[id]", params: { id: item.id } })} style={({ pressed }) => [styles.card, pressed && { opacity: .7 }]}>
      <View style={styles.top}>
        <View style={{ flex: 1 }}><Text style={styles.name}>{item.patient_name}</Text><Text style={styles.meta}>{item.reason || "Consultation"}</Text></View>
        <Pill label={item.status} tone={tone(item.status)}/>
      </View>
      <Text style={styles.time}>{new Date(item.starts_at).toLocaleString()}</Text>
    </Pressable>) : <EmptyState title="No patients booked" message="Bookings made in the citizen app appear here."/>}
  </Screen>;
}
const styles = StyleSheet.create({
  statGrid: { flexDirection: "row", gap: spacing.sm }, stat: { flex: 1, padding: spacing.md },
  label: { color: colors.secondary, fontSize: 11, fontWeight: "700" }, big: { color: colors.primary, fontSize: 26, fontWeight: "900", marginTop: 4 },
  notice: { color: colors.primaryDark, lineHeight: 19, fontSize: 13 },
  section: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: spacing.sm },
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg },
  top: { flexDirection: "row", gap: 10 }, name: { color: colors.text, fontSize: 17, fontWeight: "900" },
  meta: { color: colors.primary, marginTop: 3, fontWeight: "700", fontSize: 13 }, time: { color: colors.secondary, marginTop: spacing.md },
});
