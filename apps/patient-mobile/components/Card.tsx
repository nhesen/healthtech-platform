import type { ReactNode } from "react";
import { StyleSheet, Text, View, ViewStyle } from "react-native";
import { colors, radius, spacing } from "@/constants/theme";

export function Card({ title, eyebrow, children, style }: { title?: string; eyebrow?: string; children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>
    {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
    {title ? <Text style={styles.title}>{title}</Text> : null}
    <View style={(title || eyebrow) ? styles.body : undefined}>{children}</View>
  </View>;
}
const styles = StyleSheet.create({
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.lg },
  eyebrow: { color: colors.primary, fontSize: 12, fontWeight: "800", letterSpacing: .8, marginBottom: 5 },
  title: { color: colors.text, fontSize: 17, fontWeight: "800" }, body: { marginTop: spacing.md },
});
