import MaterialCommunityIcons from "@expo/vector-icons/MaterialCommunityIcons";
import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { AppButton } from "@/components/AppButton";
import { colors, radius, spacing } from "@/constants/theme";
import { API_URL, DEMO_MODE, login } from "@/services/api";
import { ROLE_HOME, getSession, setSession } from "@/services/session";
import type { DemoRole } from "@/types/api";

const roles: { value: DemoRole; label: string; hint: string }[] = [
  { value: "PATIENT", label: "Vətəndaş", hint: "Şəxsi sağlamlıq tarixçəsi" },
  { value: "DOCTOR", label: "Həkim", hint: "Xəstə qəbulu və konsultasiya" },
  { value: "HOSPITAL_ADMIN", label: "Xəstəxana", hint: "Çarpayı, tapşırıq və təhlükəsizlik" },
];
const DEMO_ACCOUNTS: Record<string, DemoRole> = { "1AZ0001": "PATIENT", "2AZ0002": "DOCTOR", "3AZ0003": "HOSPITAL_ADMIN" };
function cleanFin(value: string) { return value.toUpperCase().replace(/[^0-9A-Z]/g, "").slice(0, 7); }

export default function Login() {
  const [fin, setFin] = useState("");
  const [role, setRole] = useState<DemoRole>("PATIENT");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => { void getSession().then(value => { if (value) router.replace(ROLE_HOME[value.role]); }); }, []);

  function applyFin(value: string) {
    const next = cleanFin(value);
    setFin(next); setError("");
    const matched = DEMO_ACCOUNTS[next];
    if (matched) setRole(matched);
  }
  function choose(value: DemoRole) { setRole(value); setError(""); }
  function fill(code: string) { applyFin(code); }

  async function submit() {
    setLoading(true); setError("");
    try {
      const code = cleanFin(fin);
      const user = await login(code, DEMO_ACCOUNTS[code] ?? role);
      await setSession(user);
      router.replace(ROLE_HOME[user.role]);
    } catch (value) {
      setError(value instanceof Error ? value.message : "Giriş mümkün olmadı.");
    } finally { setLoading(false); }
  }

  return <SafeAreaView style={styles.safe}>
    <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <View style={styles.brand}>
        <View style={styles.logo}><MaterialCommunityIcons name="heart-pulse" size={34} color="white"/></View>
        <Text style={styles.name}>DigiSolution</Text>
        <Text style={styles.tagline}>Vahid Sağlamlıq Portalı</Text>
        <View style={styles.demo}><Text style={styles.demoText}>DEMO</Text></View>
      </View>

      <View style={styles.panel}>
        <Text style={styles.title}>Portala daxil olun</Text>
        <Text style={styles.body}>Şəxsiyyət vəsiqənizin FIN kodu və rolunuzu seçərək davam edin.</Text>

        <View>
          <Text style={styles.label}>FIN</Text>
          <TextInput
            value={fin}
            onChangeText={applyFin}
            placeholder="1AZ0001"
            placeholderTextColor={colors.secondary}
            autoCapitalize="characters"
            autoCorrect={false}
            autoComplete="off"
            textContentType="none"
            keyboardType="ascii-capable"
            maxLength={7}
            style={styles.input}
            accessibilityLabel="FIN"
          />
          <Text style={styles.hint}>7 simvol · şəxsiyyət vəsiqəsinin ön tərəfində</Text>
        </View>

        <View>
          <Text style={styles.label}>Rol seçin</Text>
          {roles.map(item =>
            <Pressable key={item.value} onPress={() => choose(item.value)} accessibilityRole="radio" accessibilityState={{ selected: role === item.value }}
              style={[styles.role, role === item.value && styles.roleActive]}>
              <MaterialCommunityIcons name={role === item.value ? "radiobox-marked" : "radiobox-blank"} size={20} color={role === item.value ? colors.primary : colors.secondary}/>
              <View style={styles.roleText}>
                <Text style={styles.roleLabel}>{item.label}</Text>
                <Text style={styles.roleHint}>{item.hint}</Text>
              </View>
            </Pressable>)}
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <AppButton label="Daxil ol" loading={loading} disabled={!DEMO_MODE || !API_URL || fin.trim().length !== 7} onPress={submit}/>
        {!API_URL ? <Text style={styles.hint}>EXPO_PUBLIC_API_URL dəyərini yayımlanmış HTTPS API-yə və ya bu kompüterin LAN ünvanına təyin edin.</Text> : null}

        <View style={styles.finBox}>
          <Text style={styles.finTitle}>DEMO FIN KODLARI · toxunub doldurun</Text>
          {roles.map(item => {
            const code = Object.keys(DEMO_ACCOUNTS).find(key => DEMO_ACCOUNTS[key] === item.value) ?? "";
            return <Pressable key={item.value} onPress={() => fill(code)} style={styles.finRow}>
              <Text style={styles.finItem}>{code} · {item.label}</Text>
            </Pressable>;
          })}
        </View>
      </View>

      <Text style={styles.disclaimer}>Sintetik demo məlumatı — real dövlət xidməti deyil.{"\n"}Qərar dəstəyi üçündür, tibbi məsləhət deyil.</Text>
    </ScrollView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.xl, gap: spacing.xl },
  brand: { alignItems: "center", marginTop: 28, gap: 6 },
  logo: { width: 68, height: 68, borderRadius: 22, backgroundColor: colors.primary, alignItems: "center", justifyContent: "center" },
  name: { marginTop: 10, color: colors.text, fontSize: 27, fontWeight: "900" },
  tagline: { color: colors.secondary, fontSize: 14 },
  demo: { marginTop: 4, backgroundColor: colors.warning, paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  demoText: { color: "white", fontSize: 11, fontWeight: "900", letterSpacing: 1 },
  panel: { borderRadius: radius.lg, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, padding: spacing.xl, gap: spacing.lg },
  title: { color: colors.text, fontSize: 22, fontWeight: "900" },
  body: { color: colors.secondary, lineHeight: 21 },
  label: { color: colors.text, fontSize: 13, fontWeight: "800", marginBottom: spacing.sm },
  input: { borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, fontSize: 18, letterSpacing: 2, color: colors.text, backgroundColor: colors.card, fontVariant: ["tabular-nums"] },
  hint: { color: colors.secondary, fontSize: 12, lineHeight: 17, marginTop: spacing.xs },
  role: { flexDirection: "row", alignItems: "center", gap: spacing.md, borderWidth: 1, borderColor: colors.border, borderRadius: radius.sm, paddingHorizontal: spacing.lg, paddingVertical: spacing.md, marginBottom: spacing.sm },
  roleActive: { borderColor: colors.primary, backgroundColor: colors.primaryLight },
  roleText: { flex: 1 },
  roleLabel: { color: colors.text, fontSize: 14, fontWeight: "800" },
  roleHint: { color: colors.secondary, fontSize: 12 },
  error: { color: colors.danger, lineHeight: 20 },
  finBox: { backgroundColor: colors.muted, borderRadius: radius.sm, padding: spacing.lg, gap: 3 },
  finTitle: { color: colors.secondary, fontSize: 11, fontWeight: "900", letterSpacing: 1, marginBottom: spacing.xs },
  finRow: { paddingVertical: 6 },
  finItem: { color: colors.text, fontSize: 13, fontWeight: "700" },
  disclaimer: { color: colors.secondary, textAlign: "center", fontSize: 11, lineHeight: 17 },
});
