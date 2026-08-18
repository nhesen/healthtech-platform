export type DemoRole = "patient@demo.az" | "doctor@demo.az" | "admin@demo.az";
const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, role: DemoRole): Promise<T> {
  const res = await fetch(`${base}${path}`, { headers: { "X-Demo-User": role }, cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
