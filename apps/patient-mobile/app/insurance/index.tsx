import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { InsuranceEstimate, Overview } from "@/types/api";

export default function Insurance() { const state = useApi(async () => { const [overview, estimate] = await Promise.all([api<Overview>(`/patients/${PATIENT_ID}/overview`), api<InsuranceEstimate>(`/insurance/estimate?patient_id=${PATIENT_ID}&doctor_id=doctor_leyla`)]); return { overview, estimate }; }, []); if (state.loading) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error}/></Screen>; const { overview, estimate } = state.data; return <Screen><PageHeader title="Insurance" subtitle="Coverage calculated by the backend" back/><Card eyebrow="YOUR PLAN" title={overview.patient.insurance_plan}><Pill label="ACTIVE" tone="green"/><Text style={styles.muted}>Synthetic demo coverage · no payment processing</Text></Card><Card title="Endocrinology estimate"><Row label="Consultation" value={`${estimate.service_price} AZN`}/><Row label={`Covered (${estimate.coverage_percent}%)`} value={`${estimate.insurance_payment} AZN`} green/><View style={styles.rule}/><Row label="You pay" value={`${estimate.patient_payment} AZN`} large/></Card><Card title="Premium Health coverage"><Row label="Endocrinology" value="80%"/><Row label="Cardiology" value="80%"/><Row label="Blood Tests" value="100%"/><Row label="MRI" value="50%"/><Row label="Dentistry" value="0%"/></Card></Screen>; }
function Row({ label, value, green, large }: { label: string; value: string; green?: boolean; large?: boolean }) { return <View style={styles.row}><Text style={[styles.label, large && styles.large]}>{label}</Text><Text style={[styles.value, green && { color: colors.success }, large && styles.large]}>{value}</Text></View>; }
const styles = StyleSheet.create({ muted: { color: colors.secondary, marginTop: spacing.md }, row: { flexDirection: "row", justifyContent: "space-between", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border }, label: { color: colors.secondary }, value: { color: colors.text, fontWeight: "900" }, large: { fontSize: 20, color: colors.text, fontWeight: "900" }, rule: { height: 4 } });
