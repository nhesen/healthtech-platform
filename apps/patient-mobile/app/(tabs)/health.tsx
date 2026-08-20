import { router } from "expo-router";
import type { Href } from "expo-router";
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
  const wbc = state.data.trends.trends.find(x => x.metric === "WBC");
  return <Screen refreshing={state.loading} onRefresh={state.reload}><PageHeader title="My Health" subtitle="Your complete health record"/><Card eyebrow="OVERVIEW" title="Health snapshot"><Text style={styles.value}>{wbc ? `${wbc.previous} → ${wbc.current} WBC` : "Complete blood count"}</Text><Text style={styles.muted}>{state.data.overview.patient.medications.length} medication · {state.data.overview.recent_activity.length} recent records</Text></Card><Card title="Explore"><ListRow icon="timeline-clock-outline" title="Timeline" subtitle="Visits, tests, and care events" onPress={() => router.push("/health/timeline")}/><ListRow icon="test-tube" title="Lab Results" subtitle="Trends, charts, and explanations" onPress={() => router.push("/health/labs")}/><ListRow icon="doctor" title="Doctor Visits" subtitle={`${state.data.overview.recent_activity.filter(x => x.type.includes("VISIT") || x.type.includes("CHECKUP")).length} recent visits`} onPress={() => router.push("/health/timeline")}/><ListRow icon="pill" title="Medications" subtitle="Current medication list" onPress={() => router.push("/health/medications")}/><ListRow icon="shield-alert-outline" title="Medication safety" subtitle="Interaction and allergy signals" onPress={() => router.push("/intelligence/medications")}/><ListRow icon="hospital-box-outline" title="Emergency card" subtitle="Blood group, allergies, medications" onPress={() => router.push("/emergency" as Href)}/><ListRow icon="file-document-multiple-outline" title="Documents" subtitle="Uploads and extracted records" onPress={() => router.push("/health/documents")}/></Card>{state.data.trends.care_navigation?.suggested_specialty ? <Card eyebrow="CARE NAVIGATION" title={state.data.trends.care_navigation.suggested_specialty}><Text style={styles.muted}>{state.data.trends.care_navigation.reason}</Text><ListRow icon="doctor" title="Find a specialist" subtitle="Browse available doctors" onPress={() => router.push("/(tabs)/doctors")}/></Card> : null}{state.data.trends.conflicts.length ? <Card eyebrow="REQUIRES REVIEW" title="Medical Record Conflict"><Text style={styles.warning}>{state.data.trends.conflicts[0].message}</Text></Card> : null}</Screen>;
}
const styles = StyleSheet.create({ value: { color: colors.text, fontSize: 25, fontWeight: "900" }, muted: { color: colors.secondary, marginTop: 6 }, warning: { color: "#B45309", lineHeight: 21 } });
