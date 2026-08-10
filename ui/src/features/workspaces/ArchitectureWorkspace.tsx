
import { useState, useEffect, useCallback, useRef, useContext } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap, addEdge,
  Connection, Node, Edge, MarkerType, BackgroundVariant,
  applyNodeChanges, applyEdgeChanges, NodeChange, EdgeChange
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { api } from '../../lib/api';
import { ActorCtx } from '../../App';

interface Props { actor: {name:string;role:string}; wsId: string; onWsChange: (id:string,name:string)=>void; }

const LAYERS = ['architecture','dataFlow','operationFlow','securityFlow'] as const;
type Layer = typeof LAYERS[number];

const PROVIDER_SERVICES: Record<string, {id:string;label:string;category:string}[]> = {
  AWS: [
    {id:'cf',label:'CloudFront',category:'NETWORK'},{id:'waf',label:'WAF',category:'SECURITY'},
    {id:'alb',label:'ALB',category:'NETWORK'},{id:'gw',label:'API Gateway',category:'GATEWAY'},
    {id:'lambda',label:'Lambda',category:'APPLICATION'},{id:'ecs',label:'ECS',category:'APPLICATION'},
    {id:'eks',label:'EKS',category:'APPLICATION'},{id:'ec2',label:'EC2',category:'APPLICATION'},
    {id:'rds',label:'RDS',category:'DATABASE'},{id:'dynamodb',label:'DynamoDB',category:'DATABASE'},
    {id:'elasticache',label:'ElastiCache',category:'CACHE'},{id:'s3',label:'S3',category:'STORAGE'},
    {id:'sqs',label:'SQS',category:'QUEUE'},{id:'sns',label:'SNS',category:'QUEUE'},
    {id:'eventbridge',label:'EventBridge',category:'QUEUE'},{id:'kms',label:'KMS',category:'SECURITY'},
    {id:'iam',label:'IAM',category:'IDENTITY'},{id:'cw',label:'CloudWatch',category:'OBSERVABILITY'},
    {id:'route53',label:'Route 53',category:'NETWORK'},
  ],
  GCP: [
    {id:'clb',label:'Cloud LB',category:'NETWORK'},{id:'cloudrun',label:'Cloud Run',category:'APPLICATION'},
    {id:'gke',label:'GKE',category:'APPLICATION'},{id:'cloudsql',label:'Cloud SQL',category:'DATABASE'},
    {id:'bigquery',label:'BigQuery',category:'DATABASE'},{id:'pubsub',label:'Pub/Sub',category:'QUEUE'},
    {id:'gcs',label:'Cloud Storage',category:'STORAGE'},{id:'monitoring',label:'Monitoring',category:'OBSERVABILITY'},
  ],
  ON_PREM: [
    {id:'app',label:'App Server',category:'APPLICATION'},{id:'k8s',label:'Kubernetes',category:'APPLICATION'},
    {id:'db',label:'Database',category:'DATABASE'},{id:'cache',label:'Cache',category:'CACHE'},
    {id:'storage',label:'Storage',category:'STORAGE'},{id:'lb',label:'Load Balancer',category:'NETWORK'},
    {id:'fw',label:'Firewall',category:'SECURITY'},{id:'vpn',label:'VPN Gateway',category:'NETWORK'},
  ],
  PRIVATE_CLOUD: [
    {id:'app',label:'App Server',category:'APPLICATION'},{id:'k8s',label:'Kubernetes',category:'APPLICATION'},
    {id:'db',label:'Database',category:'DATABASE'},{id:'cache',label:'Cache',category:'CACHE'},
    {id:'storage',label:'Storage',category:'STORAGE'},{id:'lb',label:'Load Balancer',category:'NETWORK'},
    {id:'fw',label:'Firewall',category:'SECURITY'},{id:'idp',label:'Identity Provider',category:'IDENTITY'},
  ],
};

const CAT_COLORS: Record<string,string> = {
  USER:'var(--info)', IDENTITY:'var(--warning)', SECURITY:'var(--danger)',
  NETWORK:'#a371f7', GATEWAY:'var(--accent)', APPLICATION:'var(--accent)',
  SERVICE:'var(--accent)', WORKFLOW:'var(--accent)', DATABASE:'#e3b341',
  STORAGE:'var(--info)', QUEUE:'var(--warning)', CACHE:'var(--warning)',
  OBSERVABILITY:'var(--neutral)', EXTERNAL:'var(--text-muted)',
};

function ServiceNode({ data, selected }: any) {
  return (
    <div style={{
      padding:'6px 12px', borderRadius:6, fontSize:11, fontWeight:500,
      background: selected ? 'var(--bg-active)' : 'var(--bg-surface)',
      border:`1.5px solid ${selected ? CAT_COLORS[data.category]||'var(--border-default)' : 'var(--border-default)'}`,
      color:'var(--text-primary)', cursor:'pointer', minWidth:80, textAlign:'center',
      boxShadow: selected ? `0 0 0 2px ${CAT_COLORS[data.category]}30` : 'none',
    }}>
      <div style={{fontSize:9,color:CAT_COLORS[data.category]||'var(--text-muted)',textTransform:'uppercase',letterSpacing:'0.05em',marginBottom:2}}>{data.category}</div>
      {data.label}
    </div>
  );
}
const nodeTypes = { default: ServiceNode };

export default function ArchitectureWorkspace({ actor, wsId, onWsChange }: Props) {
  const [designs, setDesigns] = useState<any[]>([]);
  const [currentDesign, setCurrentDesign] = useState<any>(null);
  const [flow, setFlow] = useState<any>(null);
  const [layer, setLayer] = useState<Layer>('architecture');
  const [msg, setMsg] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [showAI, setShowAI] = useState(false);
  const [aiForm, setAiForm] = useState({objective:'',components:'',provider:'ON_PREM',platform:'NATIVE_VM'});
  const [createForm, setCreateForm] = useState({name:'',description:'',provider:'ON_PREM',platform:'NATIVE_VM',fidelity:'LOCAL_RUNTIME'});
  const [selNode, setSelNode] = useState<any>(null);
  const [nodes, setNodes] = useState<Node[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);

  const onNodesChange = useCallback((changes: NodeChange[]) => setNodes(nds => applyNodeChanges(changes, nds)), []);
  const onEdgesChange = useCallback((changes: EdgeChange[]) => setEdges(eds => applyEdgeChanges(changes, eds)), []);
  const reactFlowInstance = useRef<any>(null);

  const loadDesigns = () => api.designs().then((d:any)=>setDesigns(d.designs||[])).catch(()=>{});

  useEffect(()=>{loadDesigns();},[]);

  // Load flow when design changes
  useEffect(()=>{
    if (!currentDesign) { setNodes([]); setEdges([]); setFlow(null); return; }
    const did = currentDesign.id||currentDesign.designId;
    api.getDesign(did).then((d:any)=>{
      const f = d.flow || d;
      setFlow(f);
      if (f?.nodes) setNodes(f.nodes.map((n:any)=>({...n,type:n.type||'default'})));
      if (f?.edges) setEdges(f.edges.map((e:any)=>({...e,markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}})));
    }).catch(()=>{});
  }, [currentDesign]);

  // Filter by layer
  const visibleNodes = layer==='architecture' ? nodes : nodes.filter(n=>flow?.layers?.[layer]?.nodes?.includes(n.id));
  const visibleEdges = layer==='architecture' ? edges : edges.filter(e=>flow?.layers?.[layer]?.edges?.includes(e.id));

  const onConnect = useCallback((params:Connection)=>setEdges(eds=>addEdge({...params,markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}},eds)),[setEdges]);

  const onNodeClick = useCallback((_:any,node:any)=>{setSelNode(node);},[]);

  const createDesign = async () => {
    try {
      const r = await api.createDesign({name:createForm.name,description:createForm.description,provider:createForm.provider,platform:createForm.platform,fidelity:createForm.fidelity});
      const did = r.id||r.designId;
      setMsg('Design created: '+did); loadDesigns(); setShowCreate(false);
      if (wsId) api.setWsDesign(wsId, did).catch(()=>{});
    } catch(e:any) { setMsg('Error: '+e.message); }
  };

  const aiGenerate = async () => {
    if (!currentDesign) return;
    const did = currentDesign.id||currentDesign.designId;
    try {
      const r = await api.post(`/api/v1/designs/${did}/ai-generate`, {brief:aiForm});
      setFlow(r.flow);
      if (r.flow?.nodes) setNodes(r.flow.nodes.map((n:any)=>({...n,type:n.type||'default'})));
      if (r.flow?.edges) setEdges(r.flow.edges.map((e:any)=>({...e,markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}})));
      setMsg('AI generated: '+r.status); setShowAI(false); loadDesigns();
    } catch(e:any) { setMsg('Error: '+e.message); }
  };

  const saveFlow = async () => {
    if (!currentDesign) return;
    const did = currentDesign.id||currentDesign.designId;
    try {
      const lyrNodes = layer==='architecture' ? nodes.map(n=>n.id) : nodes.filter(n=>flow?.layers?.[layer]?.nodes?.includes(n.id)).map(n=>n.id);
      const lyrEdges = layer==='architecture' ? edges.map(e=>e.id) : edges.filter(e=>flow?.layers?.[layer]?.edges?.includes(e.id)).map(e=>e.id);
      const updatedFlow = {...flow, nodes:nodes.map(n=>({id:n.id,type:n.type,position:n.position,data:n.data})), edges:edges.map(e=>({id:e.id,source:e.source,target:e.target,label:e.label,animated:e.animated})), layers:{...flow?.layers,[layer]:{nodes:lyrNodes,edges:lyrEdges}}};
      await api.post(`/api/v1/designs/${did}/update-flow`, {flow:updatedFlow});
      setFlow(updatedFlow); setMsg('Flow saved');
    } catch(e:any) { setMsg('Error: '+e.message); }
  };

  const addServiceNode = (svc: {id:string;label:string;category:string}) => {
    const nid = `svc-${svc.id}-${Date.now()}`;
    const nn = {id:nid,type:'default',position:{x:300+Math.random()*200,y:200+Math.random()*300},data:{label:svc.label,category:svc.category,provider:createForm.provider}};
    setNodes(nds=>[...nds,nn as Node]);
    setMsg(`Added: ${svc.label}`);
  };

  const acceptDesign = async () => {
    if (!currentDesign) return;
    try { await api.acceptDesign(currentDesign.id||currentDesign.designId); loadDesigns(); setMsg('Design accepted'); } catch(e:any){setMsg('Error: '+e.message);}
  };

  const provider = currentDesign?.provider || createForm.provider;
  const servicesList = PROVIDER_SERVICES[provider] || PROVIDER_SERVICES['ON_PREM'];

  return (
    <div style={{display:'flex',height:'calc(100vh - 88px)',gap:0,overflow:'hidden'}}>
      {/* LEFT PANEL */}
      <div style={{width:220,minWidth:220,background:'var(--bg-surface)',borderRight:'1px solid var(--border-default)',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:12,borderBottom:'1px solid var(--border-default)'}}>
          <div className="panel-title">Designs</div>
          <button className="btn btn-primary btn-sm" style={{marginTop:8,width:'100%'}} onClick={()=>setShowCreate(!showCreate)}>+ New Design</button>
          <button className="btn btn-secondary btn-sm" style={{marginTop:4,width:'100%'}} onClick={()=>setShowAI(!showAI)}>AI Generate</button>
        </div>
        <div className="flex-col" style={{flex:1,overflow:'auto',padding:'4px 8px',gap:2}}>
          {designs.map((d:any)=>(
            <button key={d.id||d.designId} onClick={()=>setCurrentDesign(d)}
              style={{textAlign:'left',padding:'6px 8px',borderRadius:4,border:'none',cursor:'pointer',fontSize:11,
                background:(currentDesign?.id||currentDesign?.designId)===(d.id||d.designId)?'var(--bg-active)':'transparent',
                color:'var(--text-secondary)'}}>
              <div style={{fontWeight:500,color:'var(--text-primary)'}}>{(d.name||(d.id||d.designId)).slice(0,20)}</div>
              <div style={{fontSize:9,color:'var(--text-muted)'}}>{d.status||'DRAFT'} · {d.provider||'?'}</div>
            </button>
          ))}
        </div>
      </div>

      {/* CENTER CANVAS */}
      <div style={{flex:1,display:'flex',flexDirection:'column',overflow:'hidden'}}>
        {/* Toolbar */}
        <div style={{height:36,minHeight:36,background:'var(--bg-surface)',borderBottom:'1px solid var(--border-default)',display:'flex',alignItems:'center',padding:'0 12px',gap:8}}>
          <span style={{fontSize:11,fontWeight:600,color:'var(--text-primary)'}}>{currentDesign?.name || currentDesign?.id || currentDesign?.designId || 'No design selected'}</span>
          {currentDesign && <span className={`badge ${currentDesign.status==='ACCEPTED'||currentDesign.status==='BASELINE_FROZEN'?'badge-success':'badge-neutral'}`} style={{fontSize:9}}>{currentDesign.status||'DRAFT'}</span>}
          <span className="badge badge-info" style={{fontSize:9}}>{currentDesign?.provider||'?'}</span>
          <span className="badge badge-neutral" style={{fontSize:9}}>{currentDesign?.platform||'?'}</span>
          <div style={{flex:1}}/>
          {/* Layer tabs */}
          {LAYERS.map(l=>(<button key={l} onClick={()=>setLayer(l)} className={`btn btn-sm ${layer===l?'btn-primary':'btn-ghost'}`} style={{fontSize:10,textTransform:'capitalize'}}>{l.replace(/([A-Z])/g,' $1')}</button>))}
          <button className="btn btn-primary btn-sm" onClick={saveFlow}>Save</button>
          {currentDesign && currentDesign.status!=='ACCEPTED' && currentDesign.status!=='BASELINE_FROZEN' && <button className="btn btn-success btn-sm" style={{background:'var(--success)',color:'#000'}} onClick={acceptDesign}>Accept</button>}
        </div>
        {/* Canvas */}
        {currentDesign ? (
          <div style={{flex:1,background:'var(--bg-root)'}}>
            <ReactFlow
              nodes={visibleNodes} edges={visibleEdges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              onConnect={onConnect} onNodeClick={onNodeClick}
              nodeTypes={nodeTypes} fitView
              defaultEdgeOptions={{markerEnd:{type:MarkerType.ArrowClosed,color:'var(--text-muted)'},style:{stroke:'var(--border-default)',strokeWidth:1.5}}}
              style={{background:'var(--bg-root)'}}
            >
              <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border-subtle)"/>
              <Controls style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:6}}/>
              <MiniMap style={{background:'var(--bg-surface)',border:'1px solid var(--border-default)',borderRadius:6}} nodeColor={n=>CAT_COLORS[(n.data as any)?.category]||'var(--text-muted)'}/>
            </ReactFlow>
          </div>
        ) : (
          <div className="empty-state" style={{flex:1}}>
            <div className="empty-state-title">Select or create a design</div>
            <div className="empty-state-desc">Choose a design from the left panel or create a new one to start designing.</div>
          </div>
        )}
      </div>

      {/* RIGHT PANEL — Inspector + Services */}
      <div style={{width:200,minWidth:200,background:'var(--bg-surface)',borderLeft:'1px solid var(--border-default)',display:'flex',flexDirection:'column',overflow:'hidden'}}>
        <div style={{padding:12,borderBottom:'1px solid var(--border-default)'}}>
          <div className="panel-title" style={{marginBottom:8}}>Services</div>
          <div style={{fontSize:9,color:'var(--text-muted)',marginBottom:8}}>{provider}</div>
          <div className="flex-col" style={{gap:2,maxHeight:300,overflow:'auto'}}>
            {servicesList.map(s=>(
              <button key={s.id} onClick={()=>addServiceNode(s)}
                style={{textAlign:'left',padding:'4px 8px',borderRadius:3,border:'none',cursor:'pointer',fontSize:10,background:'var(--bg-elevated)',color:'var(--text-secondary)',display:'flex',alignItems:'center',gap:4}}
                onMouseEnter={e=>{(e.target as HTMLElement).style.background='var(--bg-hover)'}}
                onMouseLeave={e=>{(e.target as HTMLElement).style.background='var(--bg-elevated)'}}>
                <span style={{width:6,height:6,borderRadius:'50%',background:CAT_COLORS[s.category]||'var(--text-muted)',flexShrink:0}}/>
                {s.label}
              </button>
            ))}
          </div>
        </div>
        {/* Node Inspector */}
        {selNode && (
          <div style={{padding:12,flex:1,overflow:'auto'}}>
            <div className="panel-title" style={{marginBottom:8}}>Inspector</div>
            <div style={{fontSize:10,color:'var(--text-muted',fontFamily:'monospace'}}>{selNode.id}</div>
            <div style={{fontSize:12,fontWeight:600,color:'var(--text-primary)',marginTop:4}}>{selNode.data?.label}</div>
            <div style={{fontSize:10,color:CAT_COLORS[selNode.data?.category]||'var(--text-muted)',marginTop:4}}>{selNode.data?.category}</div>
          </div>
        )}
      </div>

      {/* AI Modal */}
      {showAI && (
        <div className="modal-overlay" onClick={()=>setShowAI(false)}>
          <div className="modal-content" onClick={e=>e.stopPropagation()}>
            <div className="flex-between mb-sm"><div className="panel-title">AI Architecture Generator</div><button className="btn btn-ghost btn-sm" onClick={()=>setShowAI(false)}>×</button></div>
            {!currentDesign && <div className="text-muted mb-sm" style={{fontSize:11}}>Select or create a design first.</div>}
            <input className="form-input" placeholder="Business objective (e.g. Payment processing platform)" value={aiForm.objective} onChange={e=>setAiForm({...aiForm,objective:e.target.value})}/>
            <input className="form-input" placeholder="Key components (e.g. API, workers, database)" value={aiForm.components} onChange={e=>setAiForm({...aiForm,components:e.target.value})}/>
            <select className="form-select" value={aiForm.provider} onChange={e=>setAiForm({...aiForm,provider:e.target.value})}>
              {['AWS','GCP','ON_PREM','PRIVATE_CLOUD'].map(p=><option key={p} value={p}>{p}</option>)}
            </select>
            <select className="form-select" value={aiForm.platform} onChange={e=>setAiForm({...aiForm,platform:e.target.value})}>
              {['NATIVE_VM','KUBERNETES','OPENSHIFT_OCP','BARE_METAL'].map(p=><option key={p} value={p}>{p}</option>)}
            </select>
            <button className="btn btn-primary" onClick={aiGenerate} disabled={!currentDesign} style={{width:'100%'}}>Generate Architecture</button>
          </div>
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="modal-overlay" onClick={()=>setShowCreate(false)}>
          <div className="modal-content" onClick={e=>e.stopPropagation()}>
            <div className="flex-between mb-sm"><div className="panel-title">New Design</div><button className="btn btn-ghost btn-sm" onClick={()=>setShowCreate(false)}>×</button></div>
            <input className="form-input" placeholder="Design name" value={createForm.name} onChange={e=>setCreateForm({...createForm,name:e.target.value})}/>
            <input className="form-input" placeholder="Description" value={createForm.description} onChange={e=>setCreateForm({...createForm,description:e.target.value})}/>
            <select className="form-select" value={createForm.provider} onChange={e=>setCreateForm({...createForm,provider:e.target.value})}>{['AWS','GCP','ON_PREM','PRIVATE_CLOUD'].map(p=><option key={p} value={p}>{p}</option>)}</select>
            <select className="form-select" value={createForm.platform} onChange={e=>setCreateForm({...createForm,platform:e.target.value})}>{['NATIVE_VM','KUBERNETES','OPENSHIFT_OCP','BARE_METAL'].map(p=><option key={p} value={p}>{p}</option>)}</select>
            <button className="btn btn-primary" onClick={createDesign} style={{width:'100%'}}>Create Design</button>
          </div>
        </div>
      )}

      {/* Msg */}
      {msg && <div style={{position:'fixed',bottom:16,right:16,zIndex:100,padding:'8px 16px',background:'var(--bg-elevated)',border:'1px solid var(--border-default)',borderRadius:6,fontSize:11,color:'var(--info)',maxWidth:300}} onClick={()=>setMsg('')}>{msg}</div>}
    </div>
  );
}
