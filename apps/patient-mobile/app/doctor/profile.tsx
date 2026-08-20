import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { router } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api } from "@/services/api";
import { ROLE_LABELS, clearSession } from "@/services/session";
import type { DemoUser, DoctorAppointment } from "@/types/api";

export default function DoctorProfile() {
  const state = useApi(async () => {
    const [me, appointments] = await Promise.all([api<DemoUser>("/auth/me"), api<DoctorAppointment[]>("/appointments")]);
    return { me, appointments };
  }, []);
  async function logout() { await clearSession(); router.replace("/(auth)/login"); }
  if (state.loading && !state.data) return <Screen><LoadingState label="Loading your profile…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const { me, appointments } = state.data;
  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Profile" subtitle="Clinician account"/>
    <View style={styles.identity}>
      <View style={styles.avatar}><MaterialCommunityIcons name="doctor" size={43} color={colors.primary}/></View>
      <Text style={styles.name}>{me.name}</Text><Text style={styles.email}>{me.email}</Text>
    </View>
    <Card title="Account">
      <Detail label="Role" value={ROLE_LABELS[me.role]}/>
      <Detail label="Patients in list" value={String(appointments.length)}/>
      <Detail label="Completed today" value={String(appointments.filter(x => x.status === "COMPLETED").length)}/>
    </Card>
    <Card title="Clinical access">
      <Text style={styles.body}>A patient record opens only when there is an appointment relationship and the patient has granted consent for that category. Revoked consent closes the record immediately.</Text>
    </Card>
    <AppButton label="Sign out of demo" variant="secondary" onPress={logout}/>
    <Text style={styles.disclaimer}>All displayed identities and records are synthetic demo data.</Text>
  </Screen>;
}
function Detail({ label, value }: { label: string; value: string }) { return <View style={styles.detail}><Text style={styles.label}>{label}</Text><Text style={styles.value}>{value || "Not recorded"}</Text></View>; }
const styles = StyleSheet.create({ identity: { alignItems: "center", paddingVertical: spacing.md }, avatar: { width: 86, height: 86, borderRadius: 30, backgroundColor: colors.primaryLight, alignItems: "center", justifyContent: "center" }, name: { color: colors.text, fontSize: 24, fontWeight: "900", marginTop: spacing.md }, email: { color: colors.secondary, marginTop: 4 }, detail: { flexDirection: "row", justifyContent: "space-between", gap: 20, paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border }, label: { color: colors.secondary }, value: { color: colors.text, fontWeight: "700", flex: 1, textAlign: "right" }, body: { color: colors.secondary, lineHeight: 21 }, disclaimer: { color: colors.secondary, textAlign: "center", fontSize: 11 } });
