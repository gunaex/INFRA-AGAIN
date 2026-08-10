
import React, { useState, useEffect } from 'react';
import { FileSearch, Activity, Shield } from 'lucide-react';
import { api } from '../../lib/api';

export default function EvidenceViewer() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.runs().then((d: any) => { setRuns(d.runs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  const runsWithEvidence = runs.filter((r: any) => r.evidence || r.verification);
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Evidence Viewer</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Execution Evidence</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Before state, after state, observed state, validation, verification. Evidence is first-class.</div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Evidence Records</div></div>
        {runsWithEvidence.length === 0 ? (
          <div className="empty-state"><FileSearch size={24} className="empty-state-icon" /><div className="empty-state-title">No evidence records</div><div className="empty-state-desc">Evidence is generated after execution, observation, validation, and verification complete.</div></div>
        ) : (
          runsWithEvidence.map((r: any) => (
            <div key={r.runId || r.id} className="card" style={{ marginBottom: 12 }}>
              <div className="flex-between" style={{ marginBottom: 8 }}>
                <span className="mono">{r.runId || r.id}</span>
                <span className="badge badge-info">{r.status}</span>
              </div>
              <div className="grid-2 text-sm">
                <div><span className="text-muted">Validation: </span>{r.validation?.result || '-'}</div>
                <div><span className="text-muted">Verification: </span>{r.verification?.result || '-'}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
