import { readSession } from "./session";

export const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export const DEMO_MODE = process.env.NEXT_PUBLIC_DEMO_MODE !== "false";
export class ApiError extends Error { constructor(public status:number,message:string){super(message)} }

/** Every request acts as the signed-in demo identity; the backend still authenticates on X-Demo-User. */
export function actingUser():string{
  const session=readSession();
  if(!session)throw new ApiError(401,"Sessiya bitmişdir. Yenidən daxil olun.");
  return session.email;
}
function authHeaders(extra?:Record<string,string>):Record<string,string>{return{"X-Demo-User":actingUser(),...extra}}

async function fetchApi(path:string,init:RequestInit={}){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),path.startsWith("/documents")||path.startsWith("/cv/analyze")?180000:20000);
  try{return await fetch(`${API_BASE}${path}`,{...init,signal:controller.signal})}
  catch{throw new ApiError(0,"Unable to connect to the DigiSolution service.")}
  finally{clearTimeout(timer)}
}
async function checked<T>(res:Response):Promise<T>{
  if(res.ok)return res.json();
  const messages:Record<number,string>={401:"Your demo session is invalid or expired.",403:"You do not have permission to view this information.",404:"The requested information was not found.",409:"This action conflicts with the current state. Refresh and try again.",422:"Please check the entered information.",503:"YOLO Pose is not active. Install cv_service/requirements-vision.txt and retry."};
  throw new ApiError(res.status,messages[res.status]??"Something went wrong. Core medical data remains available.");
}
export async function api<T>(path: string): Promise<T> {
  const res = await fetchApi(path, { headers: authHeaders(), cache: "no-store" });
  return checked<T>(res);
}
export async function mutate<T>(path:string,body?:unknown):Promise<T>{
 const res=await fetchApi(path,{method:"POST",headers:authHeaders({"Content-Type":"application/json"}),body:body?JSON.stringify(body):undefined});
 return checked<T>(res);
}
export async function request<T>(path:string,method:string,body?:unknown):Promise<T>{
 const res=await fetchApi(path,{method,headers:authHeaders({"Content-Type":"application/json"}),body:body?JSON.stringify(body):undefined});
 return checked<T>(res);
}
export async function uploadFile<T>(path:string,form:FormData):Promise<T>{
 const res=await fetchApi(path,{method:"POST",headers:authHeaders(),body:form});
 return checked<T>(res);
}
export async function fetchBlob(path:string):Promise<Blob>{
 const res=await fetchApi(path,{headers:authHeaders(),cache:"no-store"});
 if(!res.ok)throw new ApiError(res.status,"The requested file is unavailable.");
 return res.blob();
}
export async function login(fin:string,role:string){
  const res=await fetchApi("/auth/login",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({fin,role})});
  if(res.status===401)throw new ApiError(401,"FIN və ya rol yanlışdır.");
  if(res.status===404)throw new ApiError(404,"Demo girişi bağlıdır.");
  if(res.status===422)throw new ApiError(422,"FIN 7 simvoldan ibarət olmalıdır.");
  if(res.status===429)throw new ApiError(429,"Çox sayda cəhd. Bir az sonra yenidən yoxlayın.");
  return checked<{id:string;name:string;email:string;role:"PATIENT"|"DOCTOR"|"HOSPITAL_ADMIN"}>(res);
}
