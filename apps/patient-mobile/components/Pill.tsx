import { StyleSheet, Text, View } from "react-native";
import { colors, radius } from "@/constants/theme";

export function Pill({ label, tone = "blue" }: { label: string; tone?: "blue" | "green" | "amber" | "red" | "gray" }) {
  return <View style={[styles.base, styles[`${tone}Box`]]}><Text style={[styles.text, styles[`${tone}Text`]]}>{label.replaceAll("_", " ")}</Text></View>;
}
const styles = StyleSheet.create({ base: { alignSelf: "flex-start", borderRadius: radius.pill, paddingHorizontal: 10, paddingVertical: 5 }, text: { fontSize: 11, fontWeight: "800" }, blueBox: { backgroundColor: colors.primaryLight }, blueText: { color: colors.primaryDark }, greenBox: { backgroundColor: "#DCFCE7" }, greenText: { color: colors.success }, amberBox: { backgroundColor: "#FEF3C7" }, amberText: { color: "#B45309" }, redBox: { backgroundColor: "#FEE2E2" }, redText: { color: colors.danger }, grayBox: { backgroundColor: colors.muted }, grayText: { color: colors.secondary } });
