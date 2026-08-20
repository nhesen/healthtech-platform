import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { RoleGate } from "@/components/RoleGate";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api } from "@/services/api";
import type { PatientFlow } from "@/types/api";

export default function FlowRoute() { return <RoleGate role="HOSPITAL_ADMIN"><Flow/></RoleGate>; }

function Flow() {
  const state = useApi(() => api<PatientFlow>(`/hospitals/${HOSPITAL_ID}/flow`), [], 5000);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading patient flow…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const peak = Math.max(1, ...state.data.stages.map(item => item.count));
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Patient flow" subtitle="Admissions by stage" back/>
    <Card eyebrow="BLOCKED" title={`${state.data.blocked} admissions held`}>
      <Text style={styles.body}>A held admission occupies a bed while a discharge blocker is open. Clearing tasks releases these beds first.</Text>
    </Card>
    {state.data.stages.length ? <Card title="Stages">{state.data.stages.map(item => <View key={item.status} style={styles.stage}>
      <View style={styles.stageTop}><Text style={styles.stageName}>{item.status.replaceAll("_", " ")}</Text><Text style={styles.stageCount}>{item.count}</Text></View>
      <View style={styles.track}><View style={[styles.fill, { width: `${Math.round(item.count / peak * 100)}%` }]}/></View>
    </View>)}</Card> : <EmptyState title="No admissions recorded"/>}
  </Screen>;
}
const styles = StyleSheet.create({
  body: { color: colors.secondary, lineHeight: 21 },
  stage: { paddingVertical: spacing.sm }, stageTop: { flexDirection: "row", justifyContent: "space-between", marginBottom: 6 },
  stageName: { color: colors.text, fontWeight: "700", fontSize: 13 }, stageCount: { color: colors.primary, fontWeight: "900" },
  track: { height: 8, borderRadius: radius.pill, backgroundColor: colors.muted, overflow: "hidden" },
  fill: { height: 8, borderRadius: radius.pill, backgroundColor: colors.primary },
});
