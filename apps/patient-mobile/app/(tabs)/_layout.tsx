import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { Redirect, Tabs } from "expo-router";
import { useEffect, useState } from "react";
import { ActivityIndicator, View } from "react-native";
import { colors } from "@/constants/theme";
import { getSession } from "@/services/session";
import type { DemoUser } from "@/types/api";

const icons: Record<string, keyof typeof MaterialCommunityIcons.glyphMap> = { index: "home-variant", health: "heart-pulse", doctors: "doctor", appointments: "calendar-clock", profile: "account-circle" };
export default function TabsLayout() {
  const [session,setSession]=useState<DemoUser|null>(),[ready,setReady]=useState(false);
  useEffect(()=>{void getSession().then(value=>{setSession(value);setReady(true)})},[]);
  if(!ready)return <View style={{flex:1,alignItems:"center",justifyContent:"center",backgroundColor:colors.background}}><ActivityIndicator size="large" color={colors.primary}/></View>;
  if(!session)return <Redirect href="/(auth)/login"/>;
  return <Tabs screenOptions={({ route }) => ({ headerShown: false, tabBarActiveTintColor: colors.primary, tabBarInactiveTintColor: colors.secondary, tabBarStyle: { height: 72, paddingTop: 8, paddingBottom: 10, borderTopColor: colors.border, backgroundColor: colors.card }, tabBarLabelStyle: { fontSize: 11, fontWeight: "700" }, tabBarIcon: ({ color, size }) => <MaterialCommunityIcons name={icons[route.name]} size={size + 1} color={color}/> })}>
    <Tabs.Screen name="index" options={{ title: "Home" }}/><Tabs.Screen name="health" options={{ title: "Health" }}/><Tabs.Screen name="doctors" options={{ title: "Doctors" }}/><Tabs.Screen name="appointments" options={{ title: "Appointments" }}/><Tabs.Screen name="profile" options={{ title: "Profile" }}/>
  </Tabs>;
}
