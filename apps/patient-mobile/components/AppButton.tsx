import type { ComponentProps } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text } from "react-native";
import { colors, radius, spacing } from "@/constants/theme";

export function AppButton({ label, variant = "primary", loading, ...props }: ComponentProps<typeof Pressable> & { label: string; variant?: "primary" | "secondary" | "danger"; loading?: boolean }) {
  const disabled = Boolean(props.disabled || loading);
  return <Pressable accessibilityRole="button" {...props} disabled={disabled} style={({ pressed }) => [styles.base, styles[variant], pressed && styles.pressed, disabled && styles.disabled]}>
    {loading ? <ActivityIndicator color={variant === "primary" ? "white" : colors.primary}/> : <Text style={[styles.label, variant !== "primary" && styles.altLabel, variant === "danger" && styles.dangerLabel]}>{label}</Text>}
  </Pressable>;
}
const styles = StyleSheet.create({
  base: { minHeight: 50, borderRadius: radius.md, paddingHorizontal: spacing.lg, alignItems: "center", justifyContent: "center", borderWidth: 1 },
  primary: { backgroundColor: colors.primary, borderColor: colors.primary }, secondary: { backgroundColor: colors.card, borderColor: colors.border }, danger: { backgroundColor: "#FEF2F2", borderColor: "#FECACA" },
  label: { color: "white", fontWeight: "800", fontSize: 15 }, altLabel: { color: colors.primary }, dangerLabel: { color: colors.danger }, pressed: { opacity: .76 }, disabled: { opacity: .45 },
});
