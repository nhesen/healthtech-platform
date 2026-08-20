import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { ListRow } from "@/components/ListRow";
import { PageHeader } from "@/components/PageHeader";
import { RoleGate } from "@/components/RoleGate";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api } from "@/services/api";
import type { DepartmentCapacity } from "@/types/api";

export default function DepartmentsRoute() { return <RoleGate role="HOSPITAL_ADMIN"><Departments/></RoleGate>; }

function Departments() {
  const state = useApi(() => api<DepartmentCapacity[]>(`/hospitals/${HOSPITAL_ID}/departments`), [], 10000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading departments…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Departments" subtitle="Beds per department" back/>
    {state.data.length ? <Card>{state.data.map(item => <ListRow key={item.id} icon="office-building-outline" title={item.name} subtitle={`${item.occupied} occupied · ${item.total_beds} beds`} right={`${item.available} free`} onPress={() => router.push({ pathname: "/hospital/beds", params: { department: item.id } })}/>)}</Card> : <EmptyState title="No departments recorded"/>}
    <View style={styles.totals}><Text style={styles.totalsText}>{state.data.reduce((sum, item) => sum + item.available, 0)} beds available across {state.data.length} departments</Text></View>
  </Screen>;
}
const styles = StyleSheet.create({ totals: { alignItems: "center" }, totalsText: { color: colors.secondary, fontSize: 12, lineHeight: 18, paddingHorizontal: spacing.md, textAlign: "center" } });
