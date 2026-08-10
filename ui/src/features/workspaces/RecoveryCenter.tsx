
import React, { useState, useEffect } from 'react';
import { RotateCcw, Activity, Shield, AlertTriangle } from 'lucide-react';
import { api } from '../../lib/api';

export default function RecoveryCenter() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.rollbackPlans().then((d: any) => { setPlans(d.rollbackPlans || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Recovery Center</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Rollback & Recovery</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Rollback executor success ≠ Recovery verified. Unknown state never equals SUCCESS.</div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Rollback Plans</div></div>
        {plans.length === 0 ? (
          <div className="empty-state"><RotateCcw size={24} className="empty-state-icon" /><div className="empty-state-title">No rollback plans</div><div className="empty-state-desc">Define rollback plans with trigger conditions, recovery steps, and verification steps.</div></div>
        ) : (
          <table className="table-compact"><thead><tr><th>ID</th><th>Status</th><th>Owner</th><th>Recovery State</th><th>Max Duration</th></tr></thead><tbody>
            {plans.map((p: any) => (
              <tr key={p.rollbackId}><td className="mono">{p.rollbackId}</td><td><span className={`badge ${p.status === 'APPROVED' ? 'badge-verified' : 'badge-draft'}`}>{p.status}</span></td><td>{p.owner || '-'}</td><td className="text-sm">{p.expectedRecoveryState || '-'}</td><td>{p.maxDurationSeconds}s</td></tr>
            ))}</tbody></table>
        )}
      </div>
    </div>
  );
}
