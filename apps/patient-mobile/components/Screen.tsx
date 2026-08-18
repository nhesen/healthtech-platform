import type { ReactNode } from "react";
import { RefreshControl, ScrollView, StyleSheet, ViewStyle } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { colors, spacing } from "@/constants/theme";

export function Screen({ children, refreshing = false, onRefresh, contentStyle }: { children: ReactNode; refreshing?: boolean; onRefresh?: () => void; contentStyle?: ViewStyle }) {
  return <SafeAreaView style={styles.safe} edges={["top", "left", "right"]}>
    <ScrollView keyboardShouldPersistTaps="handled" showsVerticalScrollIndicator={false} contentContainerStyle={[styles.content, contentStyle]} refreshControl={onRefresh ? <RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={colors.primary}/> : undefined}>
      {children}
    </ScrollView>
  </SafeAreaView>;
}
const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: colors.background }, content: { padding: spacing.lg, paddingBottom: 112, gap: spacing.lg } });
