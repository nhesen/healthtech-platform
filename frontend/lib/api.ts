export type DemoRole = "patient@demo.az" | "doctor@demo.az" | "admin@demo.az";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export async function api<T>(path: string, role: DemoRole): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { "X-Demo-User": role }, cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
export async function mutate<T>(path:string,role:DemoRole,body?:unknown):Promise<T>{
 const res=await fetch(`${API_BASE}${path}`,{method:"POST",headers:{"X-Demo-User":role,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
 if(!res.ok)throw new Error(await res.text()); return res.json();
}
export async function request<T>(path:string,role:DemoRole,method:string,body?:unknown):Promise<T>{
 const res=await fetch(`${API_BASE}${path}`,{method,headers:{"X-Demo-User":role,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
 if(!res.ok)throw new Error(await res.text()); return res.json();
}
