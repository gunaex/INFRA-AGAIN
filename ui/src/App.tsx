import React, { useState, useEffect } from 'react';

type View = 'dashboard' | 'plan' | 'run';

interface Target {
  target_type: string; name: string; provider: string; platform: string;
  mode: string; status: string; fidelity: Record<string, string>; description: string;
}

interface Capability {
  capability_id: string; name: string; provider: string; platform: string;
  lifecycle: string; fidelity: string; targets: string[];
  is_safe_to_execute: boolean; notes: string;
}

interface Run {
  run_id: string; correlation_id: string; state: string;
  provider: string; platform: string; execution_mode: string;
  created_at: string;
}

interface ArchNode { id: string; label: string; type: string; status: string; provider?: string; }
interface ArchEdge { source: string; target: string; relationship: string; }
interface ArchGraph { graph_type: string; nodes: ArchNode[]; edges: ArchEdge[]; metadata: Record<string, any>; }

interface ArchDiff { entries: Array<{node_id: string; action: string; detail: string}>; summary: string; match_count: number; missing_count: number; unexpected_count: number; }

declare const import.meta: { env: { VITE_API_URL?: string } } | undefined;
const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

async function fetchJson(url: string) { const r = await fetch(API + url); return r.json(); }

const STATUS_COLORS: Record<string, string> = {
  READY: '#22c55e', NOT_INSTALLED: '#6b7280', NOT_CONFIGURED: '#9ca3af',
  UNAVAILABLE: '#ef4444', OFFLINE: '#f59e0b', BLOCKED: '#ef4444',
  VERIFIED: '#22c55e', SUPPORTED: '#22c55e', DISCOVERED: '#3b82f6',
  UNVERIFIED: '#9ca3af', PLAN_ONLY: '#3b82f6', SIMULATED: '#f59e0b',
  LOCAL_RUNTIME: '#22c55e', OBSERVED: '#3b82f6', VALIDATED: '#22c55e',
  MISSING: '#ef4444', FAILED: '#ef4444', DRIFT: '#f59e0b',
  PLANNED: '#6b7280', PROPOSED: '#9ca3af',
};

function StatusBadge({ status }: { status: string }) {
  return <span style={{ background: STATUS_COLORS[status] || '#6b7280', color: '#fff', padding: '2px 8px', borderRadius: 4, fontSize: 12 }}>{status}</span>;
}

interface Runner { runnerId: string; name: string; version: string; os: string; status: string; capabilities?: Record<string, any>; }

function Dashboard() {
  const [targets, setTargets] = useState<Target[]>([]);
  const [caps, setCaps] = useState<Capability[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [runners, setRunners] = useState<Runner[]>([]);

  useEffect(() => {
    fetchJson('/api/v1/targets').then(d => setTargets(d.targets || []));
    fetchJson('/api/v1/capabilities?verified_only=true').then(d => setCaps(d.capabilities || []));
    fetchJson('/api/v1/runs').then(d => setRuns((d.runs || []).slice(0, 10)));
    fetchJson('/api/v1/runners').then(d => setRunners(d.runners || [])).catch(() => {});
  }, []);

  return <div style={{ padding: 24, fontFamily: 'system-ui' }}>
    <h1 style={{ margin: 0 }}>🏗️ INFRA-AGAIN</h1>
    <p style={{ color: '#6b7280' }}>Provider-Neutral Infrastructure OS</p>

    <h3>🎯 Targets</h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(250px, 1fr))', gap: 12 }}>
      {targets.map(t => <div key={t.target_type} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
        <strong>{t.name}</strong> <StatusBadge status={t.status} />
        <div style={{ fontSize: 13, color: '#6b7280' }}>{t.provider} · {t.platform} · {t.mode}</div>
      </div>)}
    </div>

    <h3>✅ Verified Capabilities</h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8 }}>
      {caps.map(c => <div key={c.capability_id} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: 8, fontSize: 13 }}>
        <strong>{c.name}</strong> <StatusBadge status={c.lifecycle} />
        <div style={{ color: '#6b7280' }}>{c.provider} · {c.fidelity}</div>
      </div>)}
    </div>

    <h3>📋 Recent Runs</h3>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {runs.map(r => <div key={r.run_id} style={{ border: '1px solid #e5e7eb', borderRadius: 6, padding: '8px 12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <span style={{ fontFamily: 'monospace', fontSize: 13 }}>{r.run_id.slice(0, 12)}…</span>
        <span style={{ fontSize: 12, color: '#6b7280' }}>{r.provider} · {r.platform}</span>
        <StatusBadge status={r.state} />
      </div>)}
    </div>

    {runners.length > 0 && <>
    <h3>🖥️ Execution Runners</h3>
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
      {runners.map(r => <div key={r.runnerId} style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <strong>{r.name || r.runnerId}</strong>
          <StatusBadge status={r.status} />
        </div>
        <div style={{ fontSize: 12, color: '#6b7280', marginTop: 4 }}>{r.os} · {r.version}</div>
        {r.capabilities && <div style={{ marginTop: 6, display: 'flex', gap: 4, flexWrap: 'wrap' }}>
          {Object.entries(r.capabilities).map(([k, v]: [string, any]) =>
            <span key={k} style={{ fontSize: 11, padding: '2px 6px', background: v.status === 'READY' ? '#dcfce7' : '#f3f4f6', borderRadius: 4 }}>
              {k}: {v.status === 'READY' ? '✅' : '○'}
            </span>
          )}
        </div>}
      </div>)}
    </div></>}
  </div>;
}

function PlanReview() {
  const [runId, setRunId] = useState('');
  const [arch, setArch] = useState<{proposed?: ArchGraph; planned?: ArchGraph; observed?: ArchGraph; diff?: ArchDiff} | null>(null);
  const [error, setError] = useState('');

  const loadArch = async () => {
    if (!runId) return;
    try {
      const d = await fetchJson(`/api/v1/runs/${runId}/architecture`);
      setArch(d.architecture);
      setError('');
    } catch { setError('Run not found'); }
  };

  return <div style={{ padding: 24, fontFamily: 'system-ui' }}>
    <h2>📐 Plan Review — Before / After</h2>
    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
      <input value={runId} onChange={e => setRunId(e.target.value)} placeholder="Run ID" style={{ padding: 8, border: '1px solid #d1d5db', borderRadius: 6, flex: 1 }} />
      <button onClick={loadArch} style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>Load</button>
    </div>
    {error && <div style={{ color: '#ef4444' }}>{error}</div>}

    {arch && <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: '0 0 8px' }}>📋 BEFORE — Planned</h3>
        {(arch.planned?.nodes || []).map(n => <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
          <StatusBadge status={n.status} /> <span>{n.label}</span>
          {n.provider && <span style={{ color: '#6b7280', fontSize: 12, marginLeft: 8 }}>{n.provider} · {n.type}</span>}
        </div>)}
      </div>
      <div style={{ border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
        <h3 style={{ margin: '0 0 8px' }}>👁️ AFTER — Observed</h3>
        {(arch.observed?.nodes || []).map(n => <div key={n.id} style={{ padding: '6px 0', borderBottom: '1px solid #f3f4f6' }}>
          <StatusBadge status={n.status} /> <span>{n.label}</span>
        </div>)}
      </div>
    </div>}

    {arch?.diff && <div style={{ marginTop: 16, border: '1px solid #e5e7eb', borderRadius: 8, padding: 16 }}>
      <h3 style={{ margin: '0 0 8px' }}>📊 Change Summary</h3>
      <div style={{ display: 'flex', gap: 16 }}>
        <span>✅ {arch.diff.match_count} Match</span>
        <span style={{ color: '#ef4444' }}>⚠️ {arch.diff.missing_count} Missing</span>
        <span style={{ color: '#f59e0b' }}>❓ {arch.diff.unexpected_count} Unexpected</span>
      </div>
      {(arch.diff.entries || []).map((e, i) => <div key={i} style={{ padding: '4px 0', fontSize: 13 }}>
        <StatusBadge status={e.action} /> {e.detail}
      </div>)}
    </div>}
  </div>;
}

function RunDetail() {
  const [runId, setRunId] = useState('');
  const [run, setRun] = useState<any>(null);

  const load = async () => {
    if (!runId) return;
    try { setRun(await fetchJson(`/api/v1/runs/${runId}`)); } catch { setRun(null); }
  };

  return <div style={{ padding: 24, fontFamily: 'system-ui' }}>
    <h2>🔍 Run Detail</h2>
    <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
      <input value={runId} onChange={e => setRunId(e.target.value)} placeholder="Run ID" style={{ padding: 8, border: '1px solid #d1d5db', borderRadius: 6, flex: 1 }} />
      <button onClick={load} style={{ padding: '8px 16px', background: '#3b82f6', color: '#fff', border: 'none', borderRadius: 6, cursor: 'pointer' }}>Load</button>
    </div>
    {run && <div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {['run_id','correlation_id','state','provider','platform','execution_mode','iac_engine','iac_version'].map(k =>
          <div key={k}><strong>{k}:</strong> {run.run?.[k] || '—'}</div>
        )}
      </div>
      <h4>Transitions ({run.transitions?.length || 0})</h4>
      {run.transitions?.map((t: any, i: number) => <div key={i} style={{ fontSize: 13, padding: '2px 0' }}>
        {t.from_state} → {t.to_state} <span style={{ color: '#6b7280' }}>{t.reason}</span>
      </div>)}
    </div>}
  </div>;
}

export default function App() {
  const [view, setView] = useState<View>('dashboard');

  const tabs: { key: View; label: string }[] = [
    { key: 'dashboard', label: '🏠 Dashboard' },
    { key: 'plan', label: '📐 Plan Review' },
    { key: 'run', label: '🔍 Run Detail' },
  ];

  return <div>
    <nav style={{ display: 'flex', gap: 0, background: '#1f2937', padding: '0 24px' }}>
      {tabs.map(t => <button key={t.key} onClick={() => setView(t.key)}
        style={{ padding: '12px 16px', border: 'none', background: view === t.key ? '#374151' : 'transparent', color: '#fff', cursor: 'pointer', fontSize: 14 }}>
        {t.label}
      </button>)}
    </nav>
    {view === 'dashboard' && <Dashboard />}
    {view === 'plan' && <PlanReview />}
    {view === 'run' && <RunDetail />}
  </div>;
}
