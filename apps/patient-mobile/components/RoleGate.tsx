import { Redirect } from "expo-router";
import { type ReactNode, useEffect, useState } from "react";
import { ActivityIndicator, StyleSheet, View } from "react-native";
import { colors } from "@/constants/theme";
import { ROLE_HOME, getSession } from "@/services/session";
import type { DemoRole, DemoUser } from "@/types/api";

/** Holds a role section until the stored session is read, then sends signed-out or mismatched roles where they belong. */
export function RoleGate({ role, children }: { role: DemoRole; children: ReactNode }) {
  const [session, setSession] = useState<DemoUser | null>();
  const [ready, setReady] = useState(false);
  useEffect(() => { void getSession().then(value => { setSession(value); setReady(true); }); }, []);
  if (!ready) return <View style={styles.center}><ActivityIndicator size="large" color={colors.primary}/></View>;
  if (!session) return <Redirect href="/(auth)/login"/>;
  if (session.role !== role) return <Redirect href={ROLE_HOME[session.role]}/>;
  return <>{children}</>;
}
const styles = StyleSheet.create({ center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.background } });
