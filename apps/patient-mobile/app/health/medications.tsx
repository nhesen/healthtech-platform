import { StyleSheet, Text } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { Patient } from "@/types/api";

export default function Medications() { const state = useApi(() => api<Patient>(`/patients/${PATIENT_ID}`), []); if (state.loading) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error}/></Screen>; const items = JSON.parse(state.data.medications_json || "[]"); return <Screen><PageHeader title="Medications" subtitle="Current medication history" back/>{items.length ? items.map((item: { name: string; dosage?: string }) => <Card key={item.name} title={item.name}><Text style={styles.dose}>{item.dosage || "Dosage not recorded"}</Text><Text style={styles.note}>Confirm medication changes with your clinician.</Text></Card>) : <EmptyState title="No medications recorded"/>}</Screen>; }
const styles = StyleSheet.create({ dose: { color: colors.text, fontSize: 20, fontWeight: "900" }, note: { color: colors.secondary, marginTop: 8 } });
