import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { StyleSheet, Text, TextInput, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { api, reviewAndConfirm } from "@/services/api";
import type { Extraction, ExtractedLab, MedicalDocument } from "@/types/api";

export default function DocumentDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const state = useApi(() => api<MedicalDocument>(`/documents/${id}`), [id]);
  const [results, setResults] = useState<ExtractedLab[]>([]);
  const [status, setStatus] = useState(""); const [busy, setBusy] = useState(false);

  const extraction: Extraction = state.data ? JSON.parse(state.data.extraction_json || "{}") : {} as Extraction;
  const confirmed = state.data?.processing_status === "CONFIRMED";
  useEffect(() => { setResults(extraction.results ?? []); }, [state.data?.id, state.data?.processing_status]);

  function update(index: number, key: keyof ExtractedLab, value: string) {
    setResults(current => current.map((item, itemIndex) => itemIndex === index ? { ...item, [key]: key === "value" ? Number(value) : value } : item));
  }

  async function confirm() {
    if (!state.data) return;
    setBusy(true); setStatus("Saving reviewed values…");
    try {
      const response = await reviewAndConfirm(state.data.id, results, extraction.report_date, extraction.source_name);
      setStatus(`Confirmed. ${response.results_created} new trusted values added; the timeline was updated.`);
      setTimeout(() => router.replace("/health/labs"), 900);
    } catch (value) {
      setStatus(value instanceof Error ? value.message : "Confirmation failed.");
    } finally { setBusy(false); }
  }

  if (state.loading && !state.data) return <Screen><LoadingState/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;

  return <Screen>
    <PageHeader title="Document" subtitle={state.data.filename} back/>
    <Card title={state.data.filename}>
      <Pill label={state.data.processing_status} tone={confirmed ? "green" : "amber"}/>
      <Text style={styles.meta}>{state.data.document_type.replaceAll("_", " ")} · {new Date(state.data.created_at).toLocaleString()}</Text>
    </Card>
    {status ? <Text style={[styles.status, status.startsWith("Confirmed") && { color: colors.success }]}>{status}</Text> : null}
    {confirmed
      ? <Card title="Extracted lab values">
          {results.length ? results.map((item, index) => <View style={styles.row} key={`${item.test_name}-${index}`}>
            <View><Text style={styles.name}>{item.test_name}</Text><Text style={styles.reference}>Reference: {item.reference_text || "Not supplied"}</Text></View>
            <Text style={styles.value}>{item.value} {item.unit}</Text>
          </View>) : <Text style={styles.meta}>No structured lab values were extracted.</Text>}
        </Card>
      : <Card title="Review extracted values">
          <Text style={styles.meta}>Values stay untrusted until you confirm them. Correct anything the parser misread.</Text>
          {results.map((item, index) => <View key={`${index}`} style={styles.edit}>
            <TextInput accessibilityLabel="Test name" value={item.test_name} onChangeText={value => update(index, "test_name", value)} style={[styles.input, { flex: 1.4 }]}/>
            <TextInput accessibilityLabel="Value" keyboardType="decimal-pad" value={String(item.value)} onChangeText={value => update(index, "value", value)} style={styles.input}/>
            <TextInput accessibilityLabel="Unit" value={item.unit} onChangeText={value => update(index, "unit", value)} style={styles.input}/>
          </View>)}
          <AppButton label="Add result" variant="secondary" onPress={() => setResults(current => [...current, { test_name: "", value: 0, unit: "", reference_text: "" }])}/>
          <AppButton label="Confirm Reviewed Data" loading={busy} disabled={!results.length || results.some(x => !x.test_name)} onPress={confirm}/>
        </Card>}
  </Screen>;
}

const styles = StyleSheet.create({ meta: { color: colors.secondary, marginTop: spacing.md, lineHeight: 20 }, row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingVertical: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border }, name: { color: colors.text, fontWeight: "800" }, reference: { color: colors.secondary, fontSize: 11, marginTop: 3 }, value: { color: colors.primaryDark, fontSize: 17, fontWeight: "900" }, status: { color: colors.primaryDark, backgroundColor: colors.primaryLight, borderRadius: 16, padding: spacing.md, lineHeight: 20, fontWeight: "700" }, edit: { flexDirection: "row", gap: 6, marginBottom: spacing.sm }, input: { flex: 1, minHeight: 48, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.background, borderRadius: 12, paddingHorizontal: 10, color: colors.text } });
