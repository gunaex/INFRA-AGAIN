
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
interface Props { actor:{name:string;role:string}; wsId:string; onWsChange:(id:string,name:string)=>void; }
export default function ArchitectureWorkspace({ actor, wsId, onWsChange }: Props) {
  const [designs,setDesigns]=useState<any[]>([]);
  const [show,setShow]=useState(false);
  const [form,setForm]=useState({name:'',description:'',provider:'ON_PREM',platform:'NATIVE_VM',fidelity:'LOCAL_RUNTIME',region:''});
  const [msg,setMsg]=useState('');
  const load=()=>api.designs().then((d:any)=>setDesigns(d.designs||[])).catch(()=>{});
  useEffect(()=>{load();},[]);
  const create=async()=>{try{const r=await api.createDesign({name:form.name,description:form.description,provider:form.provider,platform:form.platform,fidelity:form.fidelity,region:form.region});setMsg('Design created: '+(r.id||r.designId));setShow(false);load();if(wsId&&(r.id||r.designId))api.setWsDesign(wsId,r.id||r.designId).catch(()=>{});}catch(e:any){setMsg('Error: '+e.message);}};
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Architecture Workspace</div><div className="flex-between"><h2 className="page-title">Infrastructure Design</h2><button className="btn btn-primary" onClick={()=>setShow(!show)}>+ Create Design</button></div><p className="page-subtitle">Provider-neutral architecture. Provider \u2260 Platform.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    {show&&(<div className="panel mb-md">
      <div className="panel-title mb-sm">New Architecture Design</div>
      <input className="form-input" placeholder="Design name" value={form.name} onChange={e=>setForm({...form,name:e.target.value})}/>
      <input className="form-input" placeholder="Description" value={form.description} onChange={e=>setForm({...form,description:e.target.value})}/>
      <div className="grid-2"><select className="form-select" value={form.provider} onChange={e=>setForm({...form,provider:e.target.value})}>{['AWS','GCP','ON_PREM','PRIVATE_CLOUD'].map(p=><option key={p} value={p}>{p}</option>)}</select>
      <select className="form-select" value={form.platform} onChange={e=>setForm({...form,platform:e.target.value})}>{['NATIVE_VM','KUBERNETES','OPENSHIFT_OCP','BARE_METAL'].map(p=><option key={p} value={p}>{p}</option>)}</select></div>
      <select className="form-select" value={form.fidelity} onChange={e=>setForm({...form,fidelity:e.target.value})}>{['PLAN_ONLY','SIMULATED','LOCAL_RUNTIME','SANDBOX','CONTROLLED_REAL'].map(f=><option key={f} value={f}>{f}</option>)}</select>
      <div className="flex-row gap-sm"><button className="btn btn-primary" onClick={create}>Create Design</button><button className="btn btn-secondary" onClick={()=>setShow(false)}>Cancel</button></div>
    </div>)}
    <div className="panel">
      <div className="panel-header"><div className="panel-title">Designs</div></div>
      {designs.length===0?<div className="empty-state"><div className="empty-state-title">No designs yet</div></div>:<table className="data-table"><thead><tr><th>ID</th><th>Name</th><th>Provider</th><th>Status</th><th>Actions</th></tr></thead><tbody>{designs.map((d:any)=>(<tr key={d.id||d.designId}><td className="mono">{d.id||d.designId}</td><td style={{color:'var(--text-primary)'}}>{d.name||'-'}</td><td className="text-secondary">{d.provider||'-'} / {d.platform||'-'}</td><td><span className={`badge ${d.status==='ACCEPTED'||d.status==='BASELINE_FROZEN'?'badge-success':'badge-neutral'}`}>{d.status||'DRAFT'}</span></td><td className="flex-row gap-xs">{d.status!=='ACCEPTED'&&d.status!=='BASELINE_FROZEN'&&<button className="btn btn-primary btn-sm" onClick={async()=>{try{await api.acceptDesign(d.id||d.designId);load();}catch(e:any){setMsg('Error: '+e.message);}}}>Accept</button>}<button className="btn btn-ghost btn-sm" onClick={async()=>{if(wsId){await api.setWsDesign(wsId,d.id||d.designId);setMsg('Design set as current');}}}>Set Current</button></td></tr>))}</tbody></table>}
    </div>
  </div>);
}
