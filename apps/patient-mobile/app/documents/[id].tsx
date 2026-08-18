import { useLocalSearchParams } from "expo-router";
import { StyleSheet, Text, View } from "react-native";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api } from "@/services/api";
import type { Extraction, MedicalDocument } from "@/types/api";

export default function DocumentDetail() { const { id } = useLocalSearchParams<{ id: string }>(); const state = useApi(() => api<MedicalDocument>(`/documents/${id}`), [id]); if (state.loading) return <Screen><LoadingState/></Screen>; if (!state.data) return <Screen><ErrorState message={state.error}/></Screen>; const extraction: Extraction = JSON.parse(state.data.extraction_json || "{}"); return <Screen><PageHeader title="Document" subtitle={state.data.filename} back/><Card title={state.data.filename}><Pill label={state.data.processing_status} tone={state.data.processing_status === "CONFIRMED" ? "green" : "amber"}/><Text style={styles.meta}>{state.data.document_type.replaceAll("_", " ")} · {new Date(state.data.created_at).toLocaleString()}</Text></Card><Card title="Extracted lab values">{extraction.results?.length ? extraction.results.map((item, index) => <View style={styles.row} key={`${item.test_name}-${index}`}><View><Text style={styles.name}>{item.test_name}</Text><Text style={styles.reference}>Reference: {item.reference_text || "Not supplied"}</Text></View><Text style={styles.value}>{item.value} {item.unit}</Text></View>) : <Text style={styles.meta}>No structured lab values were extracted. Review is required.</Text>}</Card></Screen>; }
const styles = StyleSheet.create({ meta: { color: colors.secondary, marginTop: spacing.md, lineHeight: 20 }, row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border }, name: { color: colors.text, fontWeight: "800" }, reference: { color: colors.secondary, fontSize: 11, marginTop: 3 }, value: { color: colors.primaryDark, fontSize: 17, fontWeight: "900" } });
