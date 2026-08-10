
import React, { useState, useEffect } from 'react';
import { Play, Activity, Eye, ShieldCheck, FileSearch, CheckCircle2, FileText } from 'lucide-react';
import { api } from '../../lib/api';

export default function ExecutionCenter() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.runs().then((d: any) => { setRuns(d.runs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Execution Center</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Execution & Verification</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Executor Success ≠ Verified Success. Every stage independently validated.</div>
      </div>
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 16 }}>Execution Pipeline</div>
        <div className="grid-4">
          {[{ label: 'PLAN', icon: FileText }, { label: 'EXECUTOR', icon: Play }, { label: 'OBSERVER', icon: Eye }, { label: 'VALIDATOR', icon: ShieldCheck }, { label: 'VERIFIER', icon: CheckCircle2 }, { label: 'EVIDENCE', icon: FileSearch }].map(s => (
            <div key={s.label} className="card" style={{ textAlign: 'center' }}>
              <s.icon size={20} style={{ marginBottom: 8, color: 'var(--text-muted)' }} />
              <div className="text-xs text-muted" style={{ textTransform: 'uppercase', letterSpacing: '0.05em' }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Execution Runs</div></div>
        {runs.length === 0 ? (
          <div className="empty-state"><Play size={24} className="empty-state-icon" /><div className="empty-state-title">No execution runs</div><div className="empty-state-desc">Execute an approved implementation plan to see results here.</div></div>
        ) : (
          <table className="table-compact"><thead><tr><th>Run ID</th><th>Status</th><th>Validation</th><th>Verification</th><th>Fidelity</th></tr></thead><tbody>
            {runs.map((r: any) => (
              <tr key={r.runId || r.id}><td className="mono">{r.runId || r.id}</td><td><span className={`badge badge-${r.status === 'COMPLETED' ? 'verified' : 'info'}`}>{r.status}</span></td><td>{r.validation?.result || '-'}</td><td>{r.verification?.result || '-'}</td><td><span className="badge badge-draft">{r.fidelity || '-'}</span></td></tr>
            ))}</tbody></table>
        )}
      </div>
    </div>
  );
}
