import {notFound, redirect} from "next/navigation";

export default async function RoleLanding({params}:{params:Promise<{role:string}>}) {
  const {role}=await params;
  if(role==="patient")redirect("/patient/health");
  if(role==="doctor")redirect("/doctor/patients");
  if(role==="admin")redirect("/admin/command-center");
  notFound();
}
