import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { Tabs } from "expo-router";
import { RoleGate } from "@/components/RoleGate";
import { colors } from "@/constants/theme";

const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = { index: "view-dashboard-outline", tasks: "clipboard-check-outline", safety: "shield-alert-outline", analytics: "chart-line", profile: "account-circle" };
export default function AdminLayout() {
  return <RoleGate role="HOSPITAL_ADMIN">
    <Tabs screenOptions={({ route }) => ({ headerShown: false, tabBarActiveTintColor: colors.primary, tabBarInactiveTintColor: colors.secondary, tabBarStyle: { height: 72, paddingTop: 8, paddingBottom: 10, borderTopColor: colors.border, backgroundColor: colors.card }, tabBarLabelStyle: { fontSize: 11, fontWeight: "700" }, tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name={icons[route.name]} size={size + 1} color={color}/> })}>
      <Tabs.Screen name="index" options={{ title: "Command" }}/><Tabs.Screen name="tasks" options={{ title: "Tasks" }}/><Tabs.Screen name="safety" options={{ title: "Safety" }}/><Tabs.Screen name="analytics" options={{ title: "Analytics" }}/><Tabs.Screen name="profile" options={{ title: "Profile" }}/>
    </Tabs>
  </RoleGate>;
}
