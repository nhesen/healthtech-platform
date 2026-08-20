import { useLocalSearchParams } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { TrendChart } from "@/components/TrendChart";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { AIExplanation, LabComparison, LabResult, TrendsResponse } from "@/types/api";

export default function LabDetail() {
  const { id } = useLocalSearchParams<{ id: string }>(); const metric = decodeURIComponent(id || "WBC");
  const state = useApi(async () => {
    const [trends, labs] = await Promise.all([api<TrendsResponse>(`/patients/${PATIENT_ID}/trends`), api<LabResult[]>(`/patients/${PATIENT_ID}/lab-results`)]);
    const trend = trends.trends.find(x => x.metric === metric);
    const insight = await api<AIExplanation>(`/ai/lab-explanation/${PATIENT_ID}?metric=${encodeURIComponent(metric)}`).catch(() => undefined);
    const first = trend?.history[0]?.result_date, last = trend?.history.at(-1)?.result_date;
    const comparison = first && last && first !== last
      ? await api<LabComparison>(`/patients/${PATIENT_ID}/lab-comparison?from_date=${first}&to_date=${last}`).catch(() => undefined)
      : undefined;
    return { trend, labs: labs.filter(x => x.metric === metric), insight, comparison: comparison?.metrics.find(x => x.metric === metric), window: comparison };
  }, [metric]);
  if (state.loading && !state.data) return <Screen><LoadingState/></Screen>; if (!state.data?.trend) return <Screen><PageHeader title={metric} back/><ErrorState message={state.error || "This lab result was not found."}/></Screen>;
  const trend = state.data.trend; const reference = state.data.labs[0]?.reference_range;
  return <Screen><PageHeader title={metric} subtitle="Result history and comparison" back/><Card><View style={styles.metric}><Text style={styles.value}>{trend.current}</Text><Text style={styles.unit}>{trend.history.at(-1)?.unit}</Text></View><Text style={styles.change}>{trend.change > 0 ? "+" : ""}{trend.change} since previous · {trend.trend}</Text><Text style={styles.reference}>Reference range: {reference || "Not supplied"}</Text></Card><Card title="History"><TrendChart points={trend.history}/></Card>{state.data.comparison ? <Card eyebrow="BACKEND COMPARISON" title={`${state.data.window?.from_date} → ${state.data.window?.to_date}`}><View style={styles.row}><Text style={styles.date}>Earlier</Text><Text style={styles.result}>{state.data.comparison.from.value} {state.data.comparison.from.unit}</Text></View><View style={styles.row}><Text style={styles.date}>Latest</Text><Text style={styles.result}>{state.data.comparison.to.value} {state.data.comparison.to.unit}</Text></View><Text style={styles.change}>{state.data.comparison.change > 0 ? "+" : ""}{state.data.comparison.change} · {state.data.comparison.direction}</Text><Text style={styles.body}>{state.data.window?.explanation}</Text></Card> : null}<Card title="Measurements">{[...trend.history].reverse().map(point => <View style={styles.row} key={point.result_date}><Text style={styles.date}>{point.result_date}</Text><Text style={styles.result}>{point.value} {point.unit}</Text></View>)}</Card><Card eyebrow="AI EXPLANATION" title={state.data.insight?.ai.content.title ?? `${metric} comparison`}><Text style={styles.body}>{state.data.insight?.ai.content.explanation ?? `The latest value is ${trend.current}, compared with ${trend.previous}. This is a measured change, not a diagnosis.`}</Text><Text style={styles.advice}>{state.data.insight?.ai.content.suggested_action ?? "A clinician can review this result in context."}</Text></Card></Screen>;
}
const styles = StyleSheet.create({ metric: { flexDirection: "row", alignItems: "baseline" }, value: { color: colors.text, fontSize: 44, fontWeight: "900" }, unit: { color: colors.secondary, fontSize: 18, marginLeft: 4 }, change: { color: colors.warning, fontWeight: "800", marginTop: 4 }, reference: { color: colors.secondary, marginTop: 9 }, row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border }, date: { color: colors.secondary }, result: { color: colors.text, fontWeight: "800" }, body: { color: colors.secondary, lineHeight: 21 }, advice: { color: colors.primaryDark, fontWeight: "800", lineHeight: 20, marginTop: spacing.md } });
