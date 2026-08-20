"use client";

import {useEffect,useState} from "react";
import {useRouter} from "next/navigation";
import {ApiError,DEMO_MODE,login} from "../../lib/api";
import {ROLE_LANDING,SessionRole,readSession,writeSession} from "../../lib/session";

const roles:{value:SessionRole;label:string;hint:string}[]=[
  {value:"PATIENT",label:"Vətəndaş",hint:"Şəxsi sağlamlıq tarixçəsi"},
  {value:"DOCTOR",label:"Həkim",hint:"Klinik qərar dəstəyi"},
  {value:"HOSPITAL_ADMIN",label:"Xəstəxana",hint:"Əməliyyat idarəetməsi"},
];

export default function LoginPage(){
  const router=useRouter();
  const [fin,setFin]=useState(""),[role,setRole]=useState<SessionRole>("PATIENT"),[error,setError]=useState(""),[busy,setBusy]=useState(false);
  useEffect(()=>{const session=readSession();if(session)router.replace(ROLE_LANDING[session.role])},[router]);

  async function submit(event:React.FormEvent){
    event.preventDefault();setError("");setBusy(true);
    try{
      const user=await login(fin.trim().toUpperCase(),role);
      writeSession(user);
      router.replace(ROLE_LANDING[user.role]);
    }catch(value){
      setError(value instanceof ApiError?value.message:"Giriş mümkün olmadı. Xidmət əlçatan deyil.");
      setBusy(false);
    }
  }

  return <main className="flex min-h-screen flex-col bg-canvas">
    <header className="border-b-4 border-primary bg-white">
      <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div className="flex items-center gap-3">
          <span aria-hidden className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-lg font-black text-white">HT</span>
          <div>
            <p className="text-lg font-black leading-tight">HealthTech</p>
            <p className="text-xs text-gray-500">Vahid Sağlamlıq Portalı</p>
          </div>
        </div>
        <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-bold tracking-wider text-amber-800">DEMO</span>
      </div>
    </header>

    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center px-5 py-10">
      <section className="rounded-[22px] border border-border bg-white p-6 shadow-sm md:p-8">
        <h1 className="text-2xl font-black">Portala daxil olun</h1>
        <p className="mt-2 text-sm text-gray-500">Şəxsiyyət vəsiqənizin FIN kodu və rolunuzu seçərək davam edin.</p>

        {!DEMO_MODE?<p className="mt-6 rounded-2xl border-l-4 border-amber-500 bg-amber-50 p-4 text-sm text-amber-900">Demo rejimi bağlıdır. Davam etmək üçün istehsal autentifikasiyası konfiqurasiya olunmalıdır.</p>:
        <form className="mt-6 space-y-5" onSubmit={submit}>
          <div>
            <label className="block text-sm font-bold" htmlFor="fin">FIN</label>
            <input id="fin" name="fin" autoComplete="off" inputMode="text" maxLength={7} required
              value={fin} onChange={event=>setFin(event.target.value.toUpperCase())}
              placeholder="1AZ0001"
              className="mt-2 w-full rounded-xl border border-border px-4 py-3 font-mono text-lg tracking-[0.25em] uppercase outline-none focus:border-primary"/>
            <p className="mt-1 text-xs text-gray-500">7 simvol · şəxsiyyət vəsiqəsinin ön tərəfində</p>
          </div>

          <fieldset>
            <legend className="text-sm font-bold">Rol seçin</legend>
            <div className="mt-2 grid gap-2">
              {roles.map(item=>
                <label key={item.value} className={`flex cursor-pointer items-center gap-3 rounded-xl border px-4 py-3 ${role===item.value?"border-primary bg-blue-50":"border-border bg-white"}`}>
                  <input type="radio" name="role" value={item.value} checked={role===item.value} onChange={()=>setRole(item.value)}/>
                  <span>
                    <span className="block text-sm font-bold">{item.label}</span>
                    <span className="block text-xs text-gray-500">{item.hint}</span>
                  </span>
                </label>)}
            </div>
          </fieldset>

          {error?<p role="alert" className="rounded-xl border-l-4 border-red-600 bg-red-50 p-3 text-sm text-red-700">{error}</p>:null}

          <button type="submit" disabled={busy||fin.trim().length!==7}
            className="w-full rounded-xl bg-primary px-4 py-3 font-bold text-white disabled:cursor-not-allowed disabled:opacity-50">
            {busy?"Yoxlanılır…":"Daxil ol"}
          </button>
        </form>}

        <div className="mt-6 rounded-xl bg-gray-50 p-4">
          <p className="text-xs font-bold tracking-wider text-gray-500">DEMO FIN KODLARI</p>
          <ul className="mt-2 space-y-1 text-sm">
            <li><code className="font-mono font-bold">1AZ0001</code> · Vətəndaş</li>
            <li><code className="font-mono font-bold">2AZ0002</code> · Həkim</li>
            <li><code className="font-mono font-bold">3AZ0003</code> · Xəstəxana</li>
          </ul>
        </div>
      </section>

      <p className="mt-6 text-center text-xs leading-relaxed text-gray-500">
        Sintetik demo məlumatı — real dövlət xidməti deyil.<br/>
        Qərar dəstəyi üçündür, tibbi məsləhət deyil.
      </p>
    </div>
  </main>;
}
