import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { colors, spacing } from "@/constants/theme";

export function ListRow({ icon, title, subtitle, onPress, right }: { icon: keyof typeof MaterialCommunityIcons.glyphMap; title: string; subtitle?: string; onPress?: () => void; right?: string }) {
  return <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [styles.row, pressed && { opacity: .65 }]}><View style={styles.icon}><MaterialCommunityIcons name={icon} size={22} color={colors.primary}/></View><View style={styles.copy}><Text style={styles.title}>{title}</Text>{subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}</View>{right ? <Text style={styles.right}>{right}</Text> : null}{onPress ? <MaterialCommunityIcons name="chevron-right" size={22} color={colors.secondary}/> : null}</Pressable>;
}
const styles = StyleSheet.create({ row: { minHeight: 64, flexDirection: "row", alignItems: "center", gap: spacing.md, borderBottomWidth: 1, borderBottomColor: colors.border, paddingVertical: spacing.sm }, icon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.primaryLight, alignItems: "center", justifyContent: "center" }, copy: { flex: 1 }, title: { color: colors.text, fontWeight: "700", fontSize: 15 }, subtitle: { color: colors.secondary, fontSize: 13, marginTop: 3 }, right: { color: colors.text, fontWeight: "700", fontSize: 13 } });
