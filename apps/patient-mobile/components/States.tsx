import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";
import { AppButton } from "./AppButton";

export function LoadingState({ label = "Loading your health data…" }: { label?: string }) { return <View style={styles.state}><ActivityIndicator size="large" color={colors.primary}/><Text style={styles.text}>{label}</Text></View>; }
export function ErrorState({ message, retry }: { message: string; retry?: () => void }) { return <View style={styles.state}><MaterialCommunityIcons name="cloud-alert-outline" size={36} color={colors.warning}/><Text style={styles.title}>We could not load this</Text><Text style={styles.text}>{message}</Text>{retry ? <AppButton label="Try again" variant="secondary" onPress={retry}/> : null}</View>; }
export function EmptyState({ title = "Nothing here yet", message }: { title?: string; message?: string }) { return <View style={styles.state}><MaterialCommunityIcons name="inbox-outline" size={34} color={colors.secondary}/><Text style={styles.title}>{title}</Text>{message ? <Text style={styles.text}>{message}</Text> : null}</View>; }
const styles = StyleSheet.create({ state: { padding: spacing.xl, alignItems: "center", gap: spacing.md }, title: { color: colors.text, fontSize: 17, fontWeight: "800", textAlign: "center" }, text: { color: colors.secondary, textAlign: "center", lineHeight: 20 } });
