import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

export function PageHeader({ title, subtitle, back = false, action }: { title: string; subtitle?: string; back?: boolean; action?: { icon: keyof typeof MaterialCommunityIcons.glyphMap; onPress: () => void; badge?: number } }) {
  return <View style={styles.row}>
    {back ? <Pressable accessibilityLabel="Go back" hitSlop={12} onPress={() => router.back()} style={styles.back}><MaterialCommunityIcons name="arrow-left" size={24} color={colors.text}/></Pressable> : null}
    <View style={styles.copy}><Text style={styles.title}>{title}</Text>{subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}</View>
    {action ? <Pressable accessibilityLabel="Page action" hitSlop={10} onPress={action.onPress} style={styles.action}><MaterialCommunityIcons name={action.icon} size={23} color={colors.primary}/>{action.badge ? <View style={styles.badge}><Text style={styles.badgeText}>{Math.min(action.badge, 9)}</Text></View> : null}</Pressable> : null}
  </View>;
}
const styles = StyleSheet.create({ row: { flexDirection: "row", alignItems: "center", gap: spacing.md }, back: { width: 44, height: 44, borderRadius: 22, alignItems: "center", justifyContent: "center", backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border }, copy: { flex: 1 }, title: { color: colors.text, fontSize: 27, fontWeight: "900" }, subtitle: { marginTop: 3, color: colors.secondary, fontSize: 14 }, action: { width: 46, height: 46, borderRadius: 23, backgroundColor: colors.primaryLight, alignItems: "center", justifyContent: "center" }, badge: { position: "absolute", right: 3, top: 2, minWidth: 17, height: 17, paddingHorizontal: 3, borderRadius: 9, backgroundColor: colors.danger, alignItems: "center", justifyContent: "center" }, badgeText: { color: "white", fontSize: 10, fontWeight: "900" } });
