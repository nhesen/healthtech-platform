export type DemoRole = "patient@demo.az" | "doctor@demo.az" | "admin@demo.az";
export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export class ApiError extends Error { constructor(public status:number,message:string){super(message)} }
async function checked<T>(res:Response):Promise<T>{
  if(res.ok)return res.json();
  const messages:Record<number,string>={401:"Your demo session is invalid or expired.",403:"You do not have permission to view this information.",404:"The requested information was not found.",409:"This action conflicts with the current state. Refresh and try again.",422:"Please check the entered information."};
  throw new ApiError(res.status,messages[res.status]??"Something went wrong. Core medical data remains available.");
}
export async function api<T>(path: string, role: DemoRole): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { headers: { "X-Demo-User": role }, cache: "no-store" });
  return checked<T>(res);
}
export async function mutate<T>(path:string,role:DemoRole,body?:unknown):Promise<T>{
 const res=await fetch(`${API_BASE}${path}`,{method:"POST",headers:{"X-Demo-User":role,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
 return checked<T>(res);
}
export async function request<T>(path:string,role:DemoRole,method:string,body?:unknown):Promise<T>{
 const res=await fetch(`${API_BASE}${path}`,{method,headers:{"X-Demo-User":role,"Content-Type":"application/json"},body:body?JSON.stringify(body):undefined});
 return checked<T>(res);
}
