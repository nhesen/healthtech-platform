import { RoleGate } from "@/components/RoleGate";
import { router } from "expo-router";
import type { Href } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api, post } from "@/services/api";

export default function IntelligenceRoute() {
  return <RoleGate role="HOSPITAL_ADMIN"><Intelligence/></RoleGate>;
}
function Intelligence() {
  const state = useApi(async () => {
    const [overview, routing, match, signals] = await Promise.all([
      api<any>("/intelligence/overview"),
      post<any>("/hospitals/recommend", { severity: "CRITICAL", required_specialty: "ICU", needs_icu: true }),
      api<any[]>("/resources/match?blood_type=O-&units=4"),
      api<any[]>("/epidemics/signals"),
    ]);
    return { overview, routing, match, signals };
  }, []);
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading intelligence…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const { overview, routing, match, signals } = state.data;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Intelligence" subtitle="Connected safety and capacity" back/>
    <View style={styles.grid}>
      <Tile label="Medication alerts" value={overview.critical_medication_alerts}/>
      <Tile label="ER load" value={`${overview.hospital_capacity_percent}%`}/>
      <Tile label="Blood alerts" value={overview.blood_resource_alerts}/>
      <Tile label="Open CBC rows" value={Number(overview.population_cbc_rows || 0).toLocaleString()}/>
    </View>
    <Card title={`Route to ${routing.recommended?.name}`}>
      <Pill label={routing.priority} tone="red"/>
      {(routing.reasons || []).map((item: string) => <Text key={item} style={styles.body}>{item}</Text>)}
    </Card>
    <Card title="O− match">{match[0] ? <Text style={styles.body}>{match[0].hospital_name} · {match[0].units} units · {match[0].distance_km} km</Text> : <Text style={styles.body}>No match</Text>}</Card>
    {signals[0] ? <Card title={`Early warning · ${signals[0].region}`}><Pill label={signals[0].risk} tone="amber"/><Text style={styles.body}>{signals[0].signal} · {signals[0].change_percent}%</Text><Text style={styles.body}>{signals[0].recommendation}</Text></Card> : null}
    <AppButton label="Medication safety board" variant="secondary" onPress={() => router.push("/intelligence/medications")}/>
    <AppButton label="Emergency snapshot" variant="secondary" onPress={() => router.push("/emergency" as Href)}/>
  </Screen>;
}
function Tile({ label, value }: { label: string; value: string | number }) {
  return <Card style={styles.tile}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value}</Text></Card>;
}
const styles = StyleSheet.create({
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  tile: { width: "48%" }, label: { color: colors.secondary, fontSize: 11, fontWeight: "700" },
  value: { color: colors.primary, fontSize: 26, fontWeight: "900", marginTop: 4 },
  body: { color: colors.secondary, lineHeight: 20, marginTop: spacing.sm },
});
