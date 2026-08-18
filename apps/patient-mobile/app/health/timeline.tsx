import { StyleSheet, Text, View } from "react-native";
import { PageHeader } from "@/components/PageHeader";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { TimelineRecord } from "@/types/api";

export default function Timeline() {
  const state = useApi(() => api<TimelineRecord[]>(`/patients/${PATIENT_ID}/timeline`), []);
  if (state.loading && !state.data) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const years = [...new Set(state.data.map(item => item.record_date.slice(0, 4)))];
  return <Screen><PageHeader title="Health Timeline" subtitle="Records from your care journey" back/>{!state.data.length ? <EmptyState/> : years.map(year => <View key={year} style={styles.group}><Text style={styles.year}>{year}</Text>{state.data!.filter(item => item.record_date.startsWith(year)).map((item, index) => <View style={styles.item} key={`${item.id}-${index}`}><View style={styles.line}><View style={styles.dot}/></View><View style={styles.copy}><Text style={styles.title}>{item.title}</Text><Text style={styles.meta}>{item.record_date} · {item.type.replaceAll("_", " ")}</Text>{item.raw_text ? <Text numberOfLines={2} style={styles.detail}>{item.raw_text}</Text> : null}</View></View>)}</View>)}</Screen>;
}
const styles = StyleSheet.create({ group: { gap: 0 }, year: { color: colors.primary, fontWeight: "900", fontSize: 20, marginBottom: spacing.sm }, item: { flexDirection: "row", minHeight: 82 }, line: { width: 26, alignItems: "center", borderLeftWidth: 2, borderLeftColor: colors.border, marginLeft: 7 }, dot: { width: 14, height: 14, borderRadius: 7, backgroundColor: colors.primary, borderWidth: 3, borderColor: colors.primaryLight, marginLeft: -2 }, copy: { flex: 1, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 14, padding: 14, marginBottom: 12 }, title: { color: colors.text, fontWeight: "800", fontSize: 15 }, meta: { color: colors.secondary, marginTop: 4, fontSize: 12 }, detail: { color: colors.secondary, marginTop: 7, lineHeight: 18, fontSize: 13 } });
