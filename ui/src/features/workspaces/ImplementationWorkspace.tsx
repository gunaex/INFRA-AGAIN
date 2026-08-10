
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';
interface Props { actor:{name:string;role:string}; wsId:string; }
export default function ImplementationWorkspace({ actor, wsId }: Props) {
  const [designs,setDesigns]=useState<any[]>([]);
  const [plans,setPlans]=useState<any[]>([]);
  const [msg,setMsg]=useState('');
  const load=()=>{api.designs().then((d:any)=>setDesigns(d.designs||[])).catch(()=>{});api.runs().then((d:any)=>setPlans(d.plans||(d as any).implementation_plans||[])).catch(()=>{});};
  useEffect(()=>{load();},[]);
  const accepted=designs.filter((d:any)=>d.status==='ACCEPTED'||d.status==='BASELINE_FROZEN');
  return (<div className="page">
    <div className="mb-lg"><div className="page-eyebrow">Implementation Workspace</div><h2 className="page-title">Implementation Plans</h2><p className="page-subtitle">From accepted design to executable plan.</p></div>
    {msg&&<div className="msg-info">{msg}</div>}
    <div className="panel mb-md"><div className="panel-title mb-sm">Generate Plan</div>
      {accepted.length===0?<div className="text-muted" style={{fontSize:11}}>No accepted designs. Accept a design first in Architecture.</div>:
      <div className="flex-row gap-sm" style={{flexWrap:'wrap'}}>{accepted.slice(0,5).map((d:any)=>(<button key={d.id||d.designId} className="btn btn-primary" onClick={async()=>{try{const r=await api.createPlan(d.id||d.designId);setMsg('Plan generated: '+(r.id||r.planId||'OK'));load();if(wsId)api.setWsPlan(wsId,r.id||r.planId||'').catch(()=>{});}catch(e:any){setMsg('Error: '+e.message);}}}>Generate from {(d.name||(d.id||d.designId)).slice(0,16)}</button>))}</div>}
    </div>
    <div className="panel"><div className="panel-header"><div className="panel-title">Plans</div></div>
      {plans.length===0?<div className="empty-state"><div className="empty-state-title">No plans yet</div></div>:<table className="data-table"><thead><tr><th>Plan ID</th><th>Status</th><th>Actions</th></tr></thead><tbody>{plans.map((p:any)=>(<tr key={p.id||p.planId}><td className="mono">{p.id||p.planId}</td><td><span className={`badge ${p.status==='APPROVED_FOR_EXECUTION'?'badge-success':'badge-warning'}`}>{p.status||'DRAFT'}</span></td><td>{p.status!=='APPROVED_FOR_EXECUTION'&&<button className="btn btn-primary btn-sm" onClick={async()=>{try{await api.approvePlan(p.id||p.planId);load();setMsg('Plan approved');}catch(e:any){setMsg('Error: '+e.message);}}}>Approve</button>}</td></tr>))}</tbody></table>}
    </div>
  </div>);
}
