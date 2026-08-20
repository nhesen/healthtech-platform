"use client";

import {useEffect,useState} from "react";
import {api,request} from "../lib/api";

const button="rounded-xl bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";
const secondary="rounded-xl border border-border bg-white px-4 py-2 text-sm font-semibold";

const tone:Record<string,string>={LOW:"bg-emerald-50 text-emerald-800",MEDIUM:"bg-amber-50 text-amber-800",HIGH:"bg-orange-100 text-orange-800",CRITICAL:"bg-red-100 text-red-800","HIGH LOAD":"bg-orange-100 text-orange-800","LOW LOAD":"bg-emerald-50 text-emerald-800"};
function Pill({value}:{value:string}){return <span className={`inline-block rounded-full px-3 py-1 text-xs font-bold ${tone[value]||"bg-blue-50 text-primary"}`}>{value?.replaceAll("_"," ")}</span>}
function Card({title,children}:{title:string;children:React.ReactNode}){return <article className="rounded-2xl border border-border bg-white p-5 shadow-sm"><h2 className="font-bold">{title}</h2><div className="mt-3">{children}</div></article>}

export function IntelligenceHome(){
 const [data,setData]=useState<any>(),[error,setError]=useState("");
 useEffect(()=>{api("/intelligence/overview").then(setData).catch(()=>setError("Intelligence overview is unavailable."))},[]);
 if(error)return <p className="mt-6 text-red-700">{error}</p>;
 if(!data)return <p className="mt-6 text-gray-500">Loading intelligence…</p>;
 const tiles=[["Critical medication alerts",data.critical_medication_alerts,"/admin/medication-safety"],["Hospital ER load",`${data.hospital_capacity_percent}%`,"/admin/routing"],["Emergency routing",data.emergency_routing_cases,"/admin/routing"],["Blood resource alerts",data.blood_resource_alerts,"/admin/resources"],["Epidemiology signals",data.epidemiology_signals,"/admin/epidemics"],["Break-glass today",data.break_glass_today,"/admin/break-glass"]];
 return <div className="mt-6 grid gap-4 md:grid-cols-3">{tiles.map(([label,value,href])=><a key={label} href={href} className="rounded-2xl border border-border bg-white p-5 shadow-sm"><p className="text-xs font-bold tracking-wider text-gray-500">{label.toUpperCase()}</p><p className="mt-2 text-4xl font-bold">{value}</p></a>)}<p className="md:col-span-3 text-sm text-gray-500">{data.disclaimer}</p></div>;
}

export function MedicationSafety({role}:{role:string}){
 const [items,setItems]=useState<any[]>([]),[message,setMessage]=useState("");
 const load=()=>api<any[]>(role==="admin"?"/medication-alerts":"/medication-alerts").then(setItems).catch(()=>setMessage("Alerts could not be loaded."));
 useEffect(()=>{load()},[role]);
 async function scan(){await request("/medication-safety/scan?patient_id=patient_hasan","POST");setMessage("Hasan's medication list was re-scanned. This is decision support, not a diagnosis.");load()}
 async function setStatus(id:string,status:string){await request(`/medication-alerts/${id}`,"PATCH",{status});load()}
 return <div className="mt-6 space-y-4"><div className="flex flex-wrap gap-2"><button className={button} onClick={scan}>Scan Hasan's medications</button></div>{message&&<p className="text-sm text-amber-800">{message}</p>}{items.map(item=><Card key={item.id} title={`${item.alert_type.replaceAll("_"," ")} · ${item.patient_name}`}>
  <div className="flex flex-wrap gap-2"><Pill value={item.severity}/><Pill value={item.status}/></div>
  <p className="mt-3">{item.medication_a}{item.medication_b?` + ${item.medication_b}`:""}</p>
  <p className="mt-2 text-sm text-gray-600">{item.explanation}</p>
  <p className="mt-2 text-sm font-medium">{item.recommended_action}</p>
  <p className="mt-2 text-xs text-gray-500">{item.prescriber_a?.name} {item.prescriber_a?.specialty}{item.prescriber_b?` · ${item.prescriber_b.name} ${item.prescriber_b.specialty}`:""} · {new Date(item.created_at).toLocaleString()}</p>
  {role!=="patient"&&item.status==="NEW"?<div className="mt-3 flex gap-2"><button className={secondary} onClick={()=>setStatus(item.id,"REVIEWED")}>Mark reviewed</button><button className={secondary} onClick={()=>setStatus(item.id,"RESOLVED")}>Resolve</button></div>:null}
  <p className="mt-3 text-xs text-gray-500">{item.disclaimer}</p>
 </Card>)}</div>;
}

export function EmergencyPanel(){
 const [patientId,setPatientId]=useState("patient_hasan"),[reason,setReason]=useState("Patient unconscious"),[summary,setSummary]=useState<any>(),[message,setMessage]=useState(""),[confirm,setConfirm]=useState(false);
 async function load(){try{setSummary(await api(`/emergency/summary/${patientId}`));setMessage("")}catch{setSummary(undefined);setMessage("Normal access is blocked. Break-glass is required if this is an emergency.")}}
 async function glass(){await request("/emergency/break-glass","POST",{patient_id:patientId,reason});setConfirm(false);setMessage("Temporary emergency access is open for 5 minutes and has been audited.");load()}
 useEffect(()=>{load()},[]);
 return <div className="mt-6 grid gap-5 md:grid-cols-2">
  <Card title="Emergency lookup">
   <label className="text-sm text-gray-500">Patient ID</label>
   <input aria-label="Patient ID" className="mt-1 w-full rounded-xl border p-3" value={patientId} onChange={e=>setPatientId(e.target.value)}/>
   <button className={`${secondary} mt-3`} onClick={load}>Open if authorised</button>
   <p className="mt-4 text-sm font-semibold">Break-glass access</p>
   <p className="mt-2 text-sm text-amber-800">Emergency access will temporarily expose critical patient information. Reason is required. This action will be logged and audited.</p>
   <select aria-label="Reason" className="mt-3 w-full rounded-xl border p-3" value={reason} onChange={e=>setReason(e.target.value)}>
    <option>Patient unconscious</option><option>Emergency treatment required</option><option>Critical medical situation</option>
   </select>
   {confirm?<button className={`${button} mt-3 bg-red-600`} onClick={glass}>Confirm emergency access</button>:<button className={`${button} mt-3`} onClick={()=>setConfirm(true)}>Break-glass access</button>}
   {message&&<p className="mt-3 text-sm">{message}</p>}
  </Card>
  <Card title="Emergency patient summary">
   {summary?<>
    <p className="text-2xl font-bold">{summary.patient.name}</p>
    <p className="text-sm text-gray-500">{summary.patient.id} · Blood group {summary.patient.blood_type} · {summary.access}</p>
    <h3 className="mt-4 font-semibold">Allergies</h3>
    <p>{summary.allergies.map((x:any)=>x.name||x).join(", ")||"None recorded"}</p>
    <h3 className="mt-4 font-semibold">Current medications</h3>
    <ul className="list-disc pl-5 text-sm">{summary.medications.map((x:any,i:number)=><li key={i}>{x.name} {x.dosage} · {x.specialty||""}</li>)}</ul>
    <h3 className="mt-4 font-semibold">Chronic conditions</h3>
    <p className="text-sm">{summary.chronic_conditions.join(", ")||"None recorded"}</p>
    <h3 className="mt-4 font-semibold">Critical warnings</h3>
    {summary.critical_warnings.map((x:any,i:number)=><p key={i} className="mt-1 text-sm text-red-700">{x.severity} · {x.detail}</p>)}
    <p className="mt-4 text-xs text-gray-500">{summary.disclaimer}</p>
   </>:<p className="text-sm text-gray-500">No snapshot yet.</p>}
  </Card>
 </div>;
}

export function RoutingBoard(){
 const [network,setNetwork]=useState<any[]>([]),[result,setResult]=useState<any>();
 useEffect(()=>{api<any[]>("/hospitals/network").then(setNetwork).catch(()=>{})},[]);
 async function recommend(){setResult(await request("/hospitals/recommend","POST",{severity:"CRITICAL",required_specialty:"ICU",needs_icu:true}))}
 return <div className="mt-6 space-y-5">
  <div className="grid gap-4 md:grid-cols-2">{network.map(h=><Card key={h.id} title={h.name}><Pill value={h.load}/><p className="mt-2 text-sm">ER {h.er_load_percent}% · ICU {h.icu_available}/{h.icu_total} · Beds {h.available_beds} · Ambulances {h.ambulances} · Wait {h.avg_wait_minutes} min</p></Card>)}</div>
  <button className={button} onClick={recommend}>Recommend ICU destination</button>
  {result?.recommended&&<Card title={`Recommended: ${result.recommended.name}`}><Pill value={result.priority}/><ul className="mt-3 list-disc pl-5 text-sm">{result.reasons.map((x:string)=><li key={x}>{x}</li>)}</ul><p className="mt-3 text-sm text-gray-600">{result.ai?.content?.explanation}</p><p className="mt-2 text-xs text-gray-500">{result.disclaimer}</p></Card>}
 </div>;
}

export function ResourceBoard(){
 const [bank,setBank]=useState<any[]>([]),[match,setMatch]=useState<any>();
 useEffect(()=>{api<any[]>("/blood-bank").then(setBank).catch(()=>{})},[]);
 async function find(){setMatch(await request("/resource-matching","POST",{blood_type:"O-",units_needed:4,priority:"CRITICAL"}))}
 return <div className="mt-6 space-y-5">
  <div className="grid gap-4 md:grid-cols-2">{bank.map(item=><Card key={item.id} title={`${item.hospital_name} · ${item.blood_type}`}><p className="text-3xl font-bold">{item.units}</p><p className="text-sm text-gray-500">units on hand</p></Card>)}</div>
  <button className={button} onClick={find}>Match 4 units of O− for Caspian</button>
  {match?.best&&<Card title="Match found"><p className="text-xl font-bold">{match.best.hospital_name}</p><p>{match.best.units} compatible units · {match.best.distance_km} km · {match.best.travel_minutes} min</p><Pill value={match.best.priority}/></Card>}
 </div>;
}

export function EpidemicBoard(){
 const [signals,setSignals]=useState<any[]>([]);
 useEffect(()=>{api<any[]>("/epidemics/signals").then(setSignals).catch(()=>{})},[]);
 return <div className="mt-6 grid gap-4 md:grid-cols-2">{signals.length?signals.map(item=><Card key={item.region} title={item.region}><Pill value={item.risk}/><p className="mt-3 font-semibold">{item.signal}</p><p className="text-sm text-gray-600">Change {item.change_percent}% · confidence {Math.round(item.confidence*100)}%</p><ul className="mt-3 space-y-1 text-sm">{item.symptoms.map((s:any)=><li key={s.symptom}>{s.symptom}: {s.change_percent>0?"+":""}{s.change_percent}%</li>)}</ul><p className="mt-3 text-sm">{item.recommendation}</p></Card>):<p className="text-gray-500">No unusual activity is currently flagged.</p>}</div>;
}

export function BreakGlassLog(){
 const [items,setItems]=useState<any[]>([]);
 useEffect(()=>{api<any[]>("/emergency/access").then(setItems).catch(()=>{})},[]);
 return <div className="mt-6 space-y-3">{items.map(item=><Card key={item.id} title={item.patient_id}><p className="text-sm">{item.reason}</p><p className="text-xs text-gray-500">Opened {new Date(item.started_at).toLocaleString()} · expires {new Date(item.expires_at).toLocaleString()}{item.revoked_at?" · revoked":""}</p></Card>)}</div>;
}
