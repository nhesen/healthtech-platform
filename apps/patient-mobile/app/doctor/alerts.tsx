import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, radius, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api, patch } from "@/services/api";
import type { Notification } from "@/types/api";

export default function DoctorAlerts() {
  const state = useApi(() => api<Notification[]>("/notifications"), [], 10000);
  async function read(id: string) { await patch(`/notifications/${id}/read`); await state.reload(); }
  async function all() { await patch("/notifications/read-all"); await state.reload(); }
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading alerts…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const unread = state.data.filter(x => !x.read_at).length;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Alerts" subtitle={unread ? `${unread} unread` : "All caught up"}/>
    {unread ? <AppButton label="Mark all as read" variant="secondary" onPress={all}/> : null}
    {state.data.length ? state.data.map(item => <Pressable key={item.id} onPress={() => read(item.id)} style={[styles.item, !item.read_at && styles.unread]}>
      <View style={styles.icon}><MaterialCommunityIcons name={item.type === "SUCCESS" ? "check-circle-outline" : item.type === "WARNING" ? "alert-outline" : item.related_type === "appointment" ? "calendar-outline" : "bell-outline"} size={23} color={item.type === "WARNING" ? colors.warning : colors.primary}/></View>
      <View style={{ flex: 1 }}><Pill label={item.type} tone={item.type === "WARNING" ? "amber" : item.type === "SUCCESS" ? "green" : "blue"}/><Text style={styles.message}>{item.message}</Text><Text style={styles.time}>{new Date(item.created_at).toLocaleString()}</Text></View>
      {!item.read_at ? <View style={styles.dot}/> : null}
    </Pressable>) : <EmptyState title="No alerts yet"/>}
  </Screen>;
}
const styles = StyleSheet.create({ item: { flexDirection: "row", alignItems: "flex-start", gap: spacing.md, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg }, unread: { borderColor: "#9FC1F5", backgroundColor: "#FAFCFF" }, icon: { width: 42, height: 42, borderRadius: 14, backgroundColor: colors.primaryLight, alignItems: "center", justifyContent: "center" }, message: { color: colors.text, lineHeight: 20, fontWeight: "700", marginTop: 8 }, time: { color: colors.secondary, fontSize: 11, marginTop: 6 }, dot: { width: 9, height: 9, borderRadius: 5, backgroundColor: colors.primary } });
