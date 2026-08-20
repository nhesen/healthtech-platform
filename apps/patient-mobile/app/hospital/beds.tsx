import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { RoleGate } from "@/components/RoleGate";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api } from "@/services/api";
import type { Bed } from "@/types/api";

const FILTERS = ["All", "AVAILABLE", "OCCUPIED", "CLEANING"] as const;
type Filter = (typeof FILTERS)[number];
function tone(status: string) { return status === "AVAILABLE" ? "green" : status === "CLEANING" ? "amber" : status === "OCCUPIED" ? "blue" : "gray"; }

export default function BedsRoute() { return <RoleGate role="HOSPITAL_ADMIN"><Beds/></RoleGate>; }

function Beds() {
  const { department } = useLocalSearchParams<{ department?: string }>();
  const [filter, setFilter] = useState<Filter>("All");
  const state = useApi(() => {
    const query = new URLSearchParams();
    if (department) query.set("department_id", String(department));
    if (filter !== "All") query.set("status_filter", filter);
    const suffix = query.toString();
    return api<Bed[]>(`/hospitals/${HOSPITAL_ID}/beds${suffix ? `?${suffix}` : ""}`);
  }, [department, filter], 10000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading beds…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Beds" subtitle={department ? `Filtered by department` : "Whole hospital"} back/>
    <View style={styles.filters}>{FILTERS.map(item => <Pressable key={item} onPress={() => setFilter(item)} style={[styles.filter, filter === item && styles.active]}><Text style={[styles.filterText, filter === item && styles.activeText]}>{item === "All" ? "All" : item.toLowerCase()}</Text></Pressable>)}</View>
    {state.data.length ? state.data.map(item => <Card key={item.id}>
      <View style={styles.row}><Text style={styles.room}>Room {item.room}</Text><Pill label={item.status} tone={tone(item.status)}/></View>
      <Text style={styles.meta}>{item.department_name}</Text>
      {item.patient_name ? <Text style={styles.patient}>{item.patient_name}</Text> : null}
      {item.expected_discharge_at ? <Text style={styles.footnote}>Expected discharge {new Date(item.expected_discharge_at).toLocaleString()}</Text> : null}
    </Card>) : <EmptyState title="No beds match this filter"/>}
  </Screen>;
}
const styles = StyleSheet.create({
  filters: { flexDirection: "row", backgroundColor: colors.muted, padding: 4, borderRadius: radius.md },
  filter: { flex: 1, minHeight: 38, borderRadius: 12, alignItems: "center", justifyContent: "center" }, active: { backgroundColor: colors.card },
  filterText: { color: colors.secondary, fontWeight: "700", fontSize: 11 }, activeText: { color: colors.primaryDark },
  row: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.md },
  room: { color: colors.text, fontSize: 16, fontWeight: "900" }, meta: { color: colors.primary, fontWeight: "700", fontSize: 13, marginTop: 4 },
  patient: { color: colors.text, marginTop: spacing.sm, fontWeight: "700" }, footnote: { color: colors.secondary, fontSize: 12, marginTop: spacing.xs },
});
