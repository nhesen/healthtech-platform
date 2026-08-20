"use client";

import {useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {ROLE_LABELS,ROLE_LANDING,ROLE_SEGMENTS,Session,clearSession,readSession} from "../lib/session";

/** Renders children only for a signed-in demo identity, and only when the URL segment matches its role. */
export function SessionGate({segment,children}:{segment?:string;children:(session:Session)=>React.ReactNode}){
  const router=useRouter();
  const [session,setSession]=useState<Session|null>(null),[checked,setChecked]=useState(false);
  useEffect(()=>{const value=readSession();if(!value){router.replace("/login");return}setSession(value);setChecked(true)},[router]);

  if(!checked||!session)return <main className="min-h-screen bg-canvas p-10"><p className="mx-auto max-w-lg text-gray-500">Sessiya yoxlanılır…</p></main>;
  if(segment&&ROLE_SEGMENTS[session.role]!==segment)return <Forbidden session={session}/>;
  return <>{children(session)}</>;
}

function Forbidden({session}:{session:Session}){
  return <main className="min-h-screen bg-canvas p-5 md:p-10">
    <div className="mx-auto max-w-xl rounded-[22px] border-l-4 border-red-600 bg-white p-8 shadow-sm">
      <p className="text-xs font-bold tracking-wider text-red-700">403 · GİRİŞ QADAĞASI</p>
      <h1 className="mt-3 text-2xl font-black">Bu bölmə sizin rolunuz üçün deyil</h1>
      <p className="mt-3 text-gray-600">Siz <b>{ROLE_LABELS[session.role]}</b> kimi daxil olmusunuz. Bu panelə yalnız uyğun rol daxil ola bilər.</p>
      <div className="mt-6 flex flex-wrap gap-2">
        <a className="rounded-xl bg-primary px-4 py-3 text-sm font-bold text-white" href={ROLE_LANDING[session.role]}>Öz panelimə keç</a>
        <LogoutButton/>
      </div>
    </div>
  </main>;
}

export function LogoutButton({className}:{className?:string}){
  function signOut(){clearSession();window.location.href="/login"}
  return <button type="button" onClick={signOut} className={className??"rounded-xl border border-border bg-white px-4 py-3 text-sm font-semibold"}>Çıxış</button>;
}

export function PortalHeader({session,title,subtitle,children}:{session:Session;title:string;subtitle?:string;children?:React.ReactNode}){
  return <header className="mb-8 flex flex-col gap-4 rounded-[22px] border border-border bg-white p-6 shadow-sm md:flex-row md:items-center md:justify-between">
    <div>
      <p className="text-sm font-semibold text-primary">HEALTHTECH · {ROLE_LABELS[session.role].toUpperCase()}</p>
      <h1 className="mt-1 text-3xl font-bold">{title}</h1>
      {subtitle?<p className="mt-2 text-gray-500">{subtitle}</p>:null}
      <p className="mt-2 text-sm text-gray-500">{session.name} · <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-800">DEMO</span></p>
    </div>
    <div className="flex flex-wrap gap-2">{children}<LogoutButton/></div>
  </header>;
}
