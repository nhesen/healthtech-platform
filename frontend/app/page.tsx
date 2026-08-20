"use client";

import {useEffect,useState} from "react";
import {api,mutate,request,DEMO_MODE} from "../lib/api";
import {PortalHeader,SessionGate} from "../components/SessionGate";
import {ROLE_LANDING,Session} from "../lib/session";

type Capacity={total_beds:number;occupied:number;available:number;emergency_waiting:number};

export default function Home(){
 if(!DEMO_MODE)return <main className="min-h-screen p-10"><div className="mx-auto max-w-xl rounded-2xl border bg-white p-8"><h1 className="text-3xl font-bold">HealthTech Web Panels</h1><p className="mt-3 text-gray-600">Demo mode is disabled. Configure production authentication to continue.</p></div></main>;
 return <SessionGate>{session=><Dashboard session={session}/>}</SessionGate>;
}

function Dashboard({session}:{session:Session}){
 const [data,setData]=useState<any>(),[error,setError]=useState(""),[resetting,setResetting]=useState(false);
 const role=session.role;
 useEffect(()=>{let alive=true;const load=async()=>{try{const next=role==="DOCTOR"?{appointments:await api("/appointments"),notifications:await api("/notifications")}:role==="HOSPITAL_ADMIN"?{capacity:await api("/hospitals/hospital_caspian/capacity"),tasks:await api("/tasks"),safety:await api("/safety/events")}:{};if(alive){setData(next);setError("")}}catch{if(alive)setError("Live updates temporarily unavailable. Retrying…")}};setData(undefined);load();const timer=setInterval(load,role==="HOSPITAL_ADMIN"?3000:10000);return()=>{alive=false;clearInterval(timer)}},[role]);
 const links=role==="DOCTOR"?[["Patients","/doctor/patients"],["Alerts","/doctor/alerts"],["Consultations","/doctor/consultations"],["Medication safety","/doctor/medication-safety"],["Emergency","/doctor/emergency"]]:role==="HOSPITAL_ADMIN"?[["Command Center","/admin/command-center"],["Intelligence","/admin/intelligence"],["Medication safety","/admin/medication-safety"],["Routing","/admin/routing"],["Resources","/admin/resources"],["Epidemics","/admin/epidemics"],["Break-glass","/admin/break-glass"],["Departments","/admin/departments"],["Beds","/admin/beds"],["Patient Flow","/admin/flow"],["Tasks","/admin/tasks"],["Safety","/admin/safety"],["Analytics","/admin/analytics"]]:[["My health","/patient/health"]];
 async function resetDemo(){if(!window.confirm("Reset demo data to the starting state?"))return;setResetting(true);try{await request("/demo/reset","POST");window.location.href="/"}catch(e:any){setError(e.message);setResetting(false)}}
 return <main className="min-h-screen p-5 md:p-10"><div className="mx-auto max-w-5xl">
  <PortalHeader session={session} title={role==="PATIENT"?"Sağlamlıq portalı":"Doctor and hospital workspace."} subtitle={role==="PATIENT"?"Xəstə təcrübəsi Expo mobil tətbiqindədir.":"Patient care continues in the Expo mobile app."}>
   {role==="HOSPITAL_ADMIN"?<button onClick={resetDemo} disabled={resetting} className="rounded-2xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm font-semibold text-amber-900 disabled:opacity-50">{resetting?"Resetting…":"Reset Demo"}</button>:null}
  </PortalHeader>
  {role==="PATIENT"?<section className="mb-6 rounded-2xl border border-blue-200 bg-blue-50 p-5"><p className="text-xs font-bold tracking-wider text-primary">PATIENT EXPERIENCE</p><h2 className="mt-2 text-xl font-bold">HealthTech Patient is a native Expo app</h2><p className="mt-1 text-sm text-gray-600">Start <code>apps/patient-mobile</code>, scan its QR code in Expo Go, and sign in with FIN <code>1AZ0001</code>.</p></section>:null}
  <nav className="mb-6 flex flex-wrap gap-2">{links.map(([label,href])=><a className="rounded-xl border border-border bg-white px-3 py-2 text-sm font-semibold" key={href} href={href}>{label}</a>)}</nav>
  {error&&<div className="rounded-2xl border-l-4 border-red-600 bg-white p-5 text-red-700">{error}</div>}
  {!data&&!error&&role!=="PATIENT"&&<p className="text-gray-500">Loading secure web panel…</p>}
  {data&&role==="DOCTOR"?<DoctorView data={data}/>:null}
  {data&&role==="HOSPITAL_ADMIN"?<AdminView data={data}/>:null}
  {role==="PATIENT"?<a className="font-bold text-primary" href={ROLE_LANDING.PATIENT}>Sağlamlıq bölməmə keç →</a>:null}
 </div></main>;
}
function Card({title,children}:{title:string;children:React.ReactNode}){return <section className="rounded-2xl border border-border bg-white p-5 shadow-sm"><h2 className="font-bold">{title}</h2><div className="mt-4">{children}</div></section>}
function DoctorView({data}:{data:any}){const appointments=data.appointments as any[],unread=(data.notifications as any[]).filter(n=>!n.read_at);return <div className="grid gap-5 md:grid-cols-3"><Card title="Today&apos;s appointments"><p className="text-4xl font-bold">{appointments.length}</p></Card><Card title="Unread alerts"><p className="text-4xl font-bold text-amber-600">{unread.length}</p></Card><Card title="Waiting patients"><p className="text-4xl font-bold">{appointments.filter(a=>a.status==="WAITING").length}</p></Card><div className="md:col-span-3"><Card title="Today&apos;s patients"><ul className="space-y-3">{appointments.map(a=><li key={a.id} className="flex justify-between border-b pb-3"><span className="font-semibold">{a.patient_name}</span><span className="text-gray-500">{new Date(a.starts_at).toLocaleString()}</span></li>)}</ul></Card></div></div>}
function AdminView({data}:{data:any}){const [events,setEvents]=useState<any[]>(data.safety??[]);useEffect(()=>setEvents(data.safety??[]),[data.safety]);const capacity=data.capacity as Capacity;async function simulate(){await mutate("/cv-events",{hospital_id:"hospital_caspian",room_id:"204",event_type:"FALL_RISK",severity:"HIGH",confidence:.91,patient_state:"STANDING",previous_state:"SITTING",metadata:{source:"dashboard_simulator",demo:true}});setEvents(await api("/safety/events"))}return <div className="grid gap-5 md:grid-cols-4"><Card title="Total beds"><p className="text-3xl font-bold">{capacity.total_beds}</p></Card><Card title="Occupied"><p className="text-3xl font-bold">{capacity.occupied}</p></Card><Card title="Available"><p className="text-3xl font-bold text-green-600">{capacity.available}</p></Card><Card title="Emergency waiting"><p className="text-3xl font-bold text-red-600">{capacity.emergency_waiting}</p></Card><div className="md:col-span-2"><Card title="Priority discharge actions"><ul className="space-y-3">{data.tasks.map((t:any)=><li key={t.id} className="rounded-xl border-l-4 border-amber-500 bg-gray-50 p-4"><b>{t.title}</b> · {t.blocker_type}<br/><small>{t.impact}</small></li>)}</ul></Card></div><div className="md:col-span-2"><Card title="Patient Safety"><p className={events.find(x=>x.status!=="RESOLVED")?"font-bold text-red-700":"font-bold text-green-700"}>Room 204: {events.find(x=>x.status!=="RESOLVED")?"HIGH FALL RISK":"Stable"}</p><button onClick={simulate} className="mt-4 rounded-2xl bg-primary px-5 py-3 font-semibold text-white">Simulate Fall Risk</button></Card></div></div>}
