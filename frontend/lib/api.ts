export type DemoRole = "patient@demo.az" | "doctor@demo.az" | "admin@demo.az";
const base = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, role: DemoRole): Promise<T> {
  const res = await fetch(`${base}${path}`, { headers: { "X-Demo-User": role }, cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export async function mutate<T>(path:string,role:DemoRole,body?:unknown):Promise<T>{
 const res=await fetch(`${base}${path}`,{method:"POST",headers:{"X-Demo-User":role,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
 if(!res.ok)throw new Error(await res.text()); return res.json();
}
