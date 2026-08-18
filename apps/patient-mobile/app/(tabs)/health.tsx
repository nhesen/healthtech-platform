import { router } from "expo-router";
import { StyleSheet, Text } from "react-native";
import { Card } from "@/components/Card";
import { ListRow } from "@/components/ListRow";
import { PageHeader } from "@/components/PageHeader";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { Overview, TrendsResponse } from "@/types/api";

export default function Health() {
  const state = useApi(async () => { const [overview, trends] = await Promise.all([api<Overview>(`/patients/${PATIENT_ID}/overview`), api<TrendsResponse>(`/patients/${PATIENT_ID}/trends`)]); return { overview, trends }; }, []);
  if (state.loading && !state.data) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const hba = state.data.trends.trends.find(x => x.metric === "HbA1c");
  return <Screen refreshing={state.loading} onRefresh={state.reload}><PageHeader title="My Health" subtitle="Your complete health record"/><Card eyebrow="OVERVIEW" title="Health snapshot"><Text style={styles.value}>{hba?.current}% HbA1c</Text><Text style={styles.muted}>{state.data.overview.patient.medications.length} medication · {state.data.overview.recent_activity.length} recent records</Text></Card><Card title="Explore"><ListRow icon="timeline-clock-outline" title="Timeline" subtitle="Visits, tests, and care events" onPress={() => router.push("/health/timeline")}/><ListRow icon="test-tube" title="Lab Results" subtitle="Trends, charts, and explanations" onPress={() => router.push("/health/labs")}/><ListRow icon="doctor" title="Doctor Visits" subtitle={`${state.data.overview.recent_activity.filter(x => x.type.includes("VISIT") || x.type.includes("CHECKUP")).length} recent visits`} onPress={() => router.push("/health/timeline")}/><ListRow icon="pill" title="Medications" subtitle="Current medication list" onPress={() => router.push("/health/medications")}/><ListRow icon="file-document-multiple-outline" title="Documents" subtitle="Uploads and extracted records" onPress={() => router.push("/health/documents")}/></Card>{state.data.trends.conflicts.length ? <Card eyebrow="REQUIRES REVIEW" title="Medical Record Conflict"><Text style={styles.warning}>Conflicting allergy information requires clinical review.</Text></Card> : null}</Screen>;
}
const styles = StyleSheet.create({ value: { color: colors.text, fontSize: 25, fontWeight: "900" }, muted: { color: colors.secondary, marginTop: 6 }, warning: { color: "#B45309", lineHeight: 21 } });
