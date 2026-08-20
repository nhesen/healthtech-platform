import * as DocumentPicker from "expo-document-picker";
import * as ImagePicker from "expo-image-picker";
import { useEffect, useState } from "react";
import { Image, StyleSheet, Text, View } from "react-native";
import { AppButton } from "@/components/AppButton";
import { Card } from "@/components/Card";
import { PageHeader } from "@/components/PageHeader";
import { Pill } from "@/components/Pill";
import { Screen } from "@/components/Screen";
import { EmptyState, ErrorState, LoadingState } from "@/components/States";
import { colors, spacing } from "@/constants/theme";
import { useApi } from "@/hooks/useApi";
import { HOSPITAL_ID, api, patch, post, uploadVision, type VisionAnalysis, type VisionStatus } from "@/services/api";
import type { SafetyEvent } from "@/types/api";

export default function Safety() {
  const state = useApi(() => api<SafetyEvent[]>("/safety/events"), [], 5000);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [vision, setVision] = useState<VisionStatus>();
  const [analysis, setAnalysis] = useState<VisionAnalysis>();

  useEffect(() => {
    api<VisionStatus>("/cv/vision-status").then(setVision).catch(() => setVision({ yolo_active: false, engine: null, model: null, identity_recognition: false, frames_sent_to_api: false, install_hint: "pip install -r cv_service/requirements-vision.txt" }));
  }, []);

  async function guard(key: string, action: () => Promise<void>) {
    setBusy(key); setError("");
    try { await action(); await state.reload(); } catch (value) { setError(value instanceof Error ? value.message : "The action could not be completed."); } finally { setBusy(""); }
  }
  const simulate = () => guard("simulate", () => post("/cv-events", { hospital_id: HOSPITAL_ID, room_id: "204", event_type: "FALL_RISK", severity: "HIGH", confidence: 0.91, patient_state: "STANDING", previous_state: "SITTING", metadata: { source: "mobile_safety_board", demo: true } }));

  async function analyze(uri: string, name: string, mimeType: string) {
    await guard("vision", async () => {
      const next = await uploadVision({ uri, name, mimeType });
      setAnalysis(next);
    });
  }
  async function pickPhoto(camera = false) {
    if (camera) {
      const permission = await ImagePicker.requestCameraPermissionsAsync();
      if (!permission.granted) { setError("Camera permission is required."); return; }
    }
    const value = camera
      ? await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8 })
      : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images", "videos"], quality: 0.85 });
    if (!value.canceled) {
      const item = value.assets[0];
      const isVideo = (item.mimeType || "").startsWith("video") || /\.(mp4|mov|webm)$/i.test(item.fileName || item.uri);
      await analyze(item.uri, item.fileName || (isVideo ? "corridor.mp4" : "corridor.jpg"), item.mimeType || (isVideo ? "video/mp4" : "image/jpeg"));
    }
  }
  async function pickVideo() {
    const value = await DocumentPicker.getDocumentAsync({ type: ["video/mp4", "video/quicktime", "video/webm"], copyToCacheDirectory: true });
    if (!value.canceled) await analyze(value.assets[0].uri, value.assets[0].name, value.assets[0].mimeType || "video/mp4");
  }

  if (state.loading && !state.data) return <Screen><LoadingState label="Loading the safety board…"/></Screen>;
  if (!state.data) return <Screen><ErrorState message={state.error} retry={state.reload}/></Screen>;
  const active = state.data.find(item => item.status !== "RESOLVED");
  const fall = state.data.find(item => item.status !== "RESOLVED" && ["FALL_RISK", "PATIENT_STANDING", "OUT_OF_BED"].includes(item.event_type));
  const history = state.data.filter(item => item.id !== active?.id);

  return <Screen refreshing={state.loading} onRefresh={state.reload}>
    <PageHeader title="Patient safety" subtitle="Camera events, corridor occupancy, and nurse dispatch"/>
    {error ? <Text style={styles.error}>{error}</Text> : null}

    <Card title="Corridor vision">
      <View style={styles.row}><Pill label={vision?.yolo_active ? "YOLO ACTIVE" : "YOLO INACTIVE"} tone={vision?.yolo_active ? "green" : "amber"}/><Text style={styles.meta}>no identity</Text></View>
      <Text style={styles.body}>Upload a corridor photo or video. YOLO Pose counts people and pose changes. The file is discarded after analysis.</Text>
      {vision?.install_hint && !vision.yolo_active ? <Text style={styles.footnote}>{vision.install_hint}</Text> : null}
      <View style={styles.actions}>
        <AppButton label="Choose photo or video" variant="secondary" loading={busy === "vision"} disabled={Boolean(busy)} onPress={() => pickPhoto(false)}/>
        <AppButton label="Take photo" variant="secondary" disabled={Boolean(busy)} onPress={() => pickPhoto(true)}/>
        <AppButton label="Choose video file" variant="secondary" disabled={Boolean(busy)} onPress={pickVideo}/>
      </View>
      {analysis ? <>
        {analysis.overlay_image?.base64 ? <Image accessibilityLabel="YOLO occupancy overlay" source={{ uri: `data:${analysis.overlay_image.mime};base64,${analysis.overlay_image.base64}` }} style={styles.overlay} resizeMode="contain"/> : null}
        <Text style={styles.historyLine}>{analysis.crowding?.level ?? "UNKNOWN"} · peak {analysis.peak_people ?? 0} people</Text>
        <Text style={styles.footnote}>Qırmızı qutu = aşkarlanan şəxs və ehtimal.</Text>
        <Text style={styles.footnote}>{analysis.crowding?.explanation}</Text>
        <Text style={styles.footnote}>{analysis.movement?.explanation}</Text>
        <Text style={styles.footnote}>{(analysis.movement?.transitions || []).join(", ") || "No pose transition"} · {analysis.engine || "inactive"}</Text>
      </> : null}
    </Card>

    {active ? <Card eyebrow={`ROOM ${active.room_id}`} title={active.event_type.replaceAll("_", " ")}>
      <View style={styles.row}><Pill label={active.status ?? "ACTIVE"} tone={active.status === "ACKNOWLEDGED" ? "amber" : "red"}/><Pill label={fall ? "FALL RISK" : active.event_type === "OVERCROWDING" ? "CROWDED" : "STABLE"} tone={fall ? "red" : "amber"}/><Text style={styles.meta}>{Math.round(active.confidence * 100)}%</Text></View>
      <Text style={styles.body}>{(active.previous_state ?? "unknown").toLowerCase()} → {(active.patient_state ?? "unknown").toLowerCase()}</Text>
      <Text style={styles.footnote}>Detected {new Date(active.occurred_at).toLocaleString()}</Text>
      <View style={styles.actions}>
        {active.status === "ACTIVE" ? <AppButton label="Acknowledge" loading={busy === "ack"} disabled={Boolean(busy)} onPress={() => guard("ack", () => patch(`/cv-events/${active.id}/acknowledge`))}/> : null}
        <AppButton label="Send nurse" variant="secondary" loading={busy === "nurse"} disabled={Boolean(busy)} onPress={() => guard("nurse", () => post(`/cv-events/${active.id}/send-nurse`))}/>
        {active.status === "ACKNOWLEDGED" ? <AppButton label="Resolve event" variant="secondary" loading={busy === "resolve"} disabled={Boolean(busy)} onPress={() => guard("resolve", () => patch(`/cv-events/${active.id}/resolve`))}/> : null}
      </View>
      {active.nurse_tasks.length ? <View style={styles.tasks}><Text style={styles.tasksTitle}>Nurse tasks</Text>{active.nurse_tasks.map(task => <View key={task.id} style={styles.task}><Text style={styles.taskTitle}>{task.title}</Text><Text style={styles.footnote}>{task.assigned_role} · {task.priority} · {task.status}</Text></View>)}</View> : null}
    </Card> : <Card title="No active event">
      <Text style={styles.body}>Camera monitoring is idle. Simulate a fall-risk event, or upload a corridor scene for YOLO occupancy analysis.</Text>
      <AppButton label="Simulate fall risk" loading={busy === "simulate"} disabled={Boolean(busy)} onPress={simulate}/>
    </Card>}

    <Text style={styles.section}>History</Text>
    {history.length ? history.slice(0, 20).map(item => <Card key={item.id}>
      <View style={styles.row}><Pill label={item.status ?? "LOGGED"} tone={item.status === "RESOLVED" ? "green" : item.status === "ACKNOWLEDGED" ? "amber" : "red"}/><Text style={styles.meta}>Room {item.room_id}</Text></View>
      <Text style={styles.historyLine}>{item.event_type.replaceAll("_", " ")} · {Math.round(item.confidence * 100)}%</Text>
      <Text style={styles.footnote}>{new Date(item.occurred_at).toLocaleString()}{item.resolved_at ? ` · resolved ${new Date(item.resolved_at).toLocaleTimeString()}` : ""}</Text>
    </Card>) : <EmptyState title="No earlier events"/>}
  </Screen>;
}
const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  meta: { color: colors.secondary, fontSize: 12, marginLeft: "auto" },
  body: { color: colors.secondary, lineHeight: 21, marginTop: spacing.md },
  footnote: { color: colors.secondary, fontSize: 12, lineHeight: 18, marginTop: spacing.xs },
  actions: { gap: spacing.sm, marginTop: spacing.lg },
  tasks: { marginTop: spacing.lg, backgroundColor: colors.muted, borderRadius: 12, padding: spacing.md },
  tasksTitle: { color: colors.text, fontWeight: "800", fontSize: 13, marginBottom: spacing.sm },
  task: { paddingVertical: spacing.xs }, taskTitle: { color: colors.text, fontWeight: "700" },
  section: { color: colors.text, fontSize: 19, fontWeight: "900", marginTop: spacing.sm },
  historyLine: { color: colors.text, fontWeight: "700", marginTop: spacing.sm },
  overlay: { width: "100%", height: 240, marginTop: spacing.md, borderRadius: 12, backgroundColor: colors.muted },
  error: { color: colors.danger, lineHeight: 20 },
});
