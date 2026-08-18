import { StyleSheet, Text, View, useWindowDimensions } from "react-native";
import Svg, { Circle, Line, Path } from "react-native-svg";
import { colors } from "@/constants/theme";
import type { LabPoint } from "@/types/api";

export function TrendChart({ points }: { points: LabPoint[] }) {
  const { width } = useWindowDimensions(); const chartWidth = Math.max(240, Math.min(width - 66, 430)); const height = 150;
  if (!points.length) return null;
  const values = points.map(p => p.value); const min = Math.min(...values) - .3; const max = Math.max(...values) + .3;
  const coords = points.map((point, index) => ({ x: 18 + index * ((chartWidth - 36) / Math.max(1, points.length - 1)), y: 18 + (max - point.value) / Math.max(.1, max - min) * (height - 42), point }));
  const path = coords.map((p, index) => `${index ? "L" : "M"}${p.x},${p.y}`).join(" ");
  return <View><Svg width={chartWidth} height={height}><Line x1="18" y1={height - 24} x2={chartWidth - 18} y2={height - 24} stroke={colors.border} strokeWidth="1"/><Path d={path} fill="none" stroke={colors.primary} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>{coords.map(({ x, y }) => <Circle key={`${x}-${y}`} cx={x} cy={y} r="6" fill={colors.card} stroke={colors.primary} strokeWidth="3"/>)}</Svg><View style={styles.labels}>{coords.map(({ point }) => <View key={point.result_date}><Text style={styles.year}>{point.result_date.slice(0,4)}</Text><Text style={styles.value}>{point.value}</Text></View>)}</View></View>;
}
const styles = StyleSheet.create({ labels: { flexDirection: "row", justifyContent: "space-between", paddingHorizontal: 8 }, year: { color: colors.secondary, fontSize: 12, textAlign: "center" }, value: { color: colors.text, fontWeight: "800", textAlign: "center", marginTop: 2 } });
