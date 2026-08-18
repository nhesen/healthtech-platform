import { router } from "expo-router";
import { StyleSheet, Text } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { PATIENT_ID, api } from "@/services/api";
import type { MedicalDocument } from "@/types/api";

export default function Documents() { const state = useApi(() => api<MedicalDocument[]>(`/documents?patient_id=${PATIENT_ID}`), []); if (state.loading && !state.data) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error}/></Screen>; return <Screen><PageHeader title="Documents" subtitle="Reports processed by the backend" back/><AppButton label="Upload document" onPress={() => router.push("/documents/upload")}/>{!state.data.length ? <EmptyState title="No documents uploaded"/> : state.data.map(item => <Card title={item.filename} key={item.id}><Pill label={item.processing_status} tone={item.processing_status === "CONFIRMED" ? "green" : "amber"}/><Text style={styles.meta}>{item.document_type.replaceAll("_", " ")} · {new Date(item.created_at).toLocaleDateString()}</Text><AppButton label="Open" variant="secondary" onPress={() => router.push({ pathname: "/documents/[id]", params: { id: item.id } })}/></Card>)}</Screen>; }
const styles = StyleSheet.create({ meta: { color: colors.secondary, marginVertical: 12 } });
