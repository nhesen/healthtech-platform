import { StyleSheet, Text, View } from "react-native";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { RoleGate } from "@/components/RoleGate";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { AuditEvent } from "@/types/api";

export default function AuditRoute() { return <RoleGate role="HOSPITAL_ADMIN"><Audit/></RoleGate>; }

function Audit() {
  const state = useApi(() => api<AuditEvent[]>("/audit"), [], 10000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading the audit trail…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Audit trail" subtitle="Operational events, newest first" back/>
    {state.data.length ? state.data.slice(0, 40).map(item => <View key={item.id} style={styles.item}>
      <Pill label={item.event_type} tone="gray"/>
      <Text style={styles.entity}>{item.entity_type} · {item.entity_id}</Text>
      <Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text>
    </View>) : <EmptyState title="No audit events yet"/>}
    <Text style={styles.footnote}>Every bed, task, admission, and safety action is written to this trail.</Text>
  </Screen>;
}
const styles = StyleSheet.create({
  item: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg, gap: spacing.sm },
  entity: { color: colors.text, fontWeight: "700", fontSize: 13 }, time: { color: colors.secondary, fontSize: 11 },
  footnote: { color: colors.secondary, fontSize: 12, textAlign: "center", lineHeight: 18 },
});
