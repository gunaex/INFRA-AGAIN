
import React, { useState, useEffect } from 'react';
import { FileText, Shield, Activity, Clock, AlertTriangle } from 'lucide-react';
import { api } from '../../lib/api';

export default function ImplementationWorkspace() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.implementationPlans().then((d: any) => { setPlans(d.plans || d.implementation_plans || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Implementation Workspace</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Implementation Plans</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>From architecture design to executable plan. Baseline frozen before execution.</div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Plans</div></div>
        {plans.length === 0 ? (
          <div className="empty-state"><FileText size={24} className="empty-state-icon" /><div className="empty-state-title">No implementation plans</div><div className="empty-state-desc">Create an implementation plan from an accepted architecture design.</div></div>
        ) : (
          <table className="table-compact"><thead><tr><th>Plan ID</th><th>Design ID</th><th>Status</th><th>Checksum</th><th>Created</th></tr></thead><tbody>
            {plans.map((p: any) => (
              <tr key={p.id || p.planId}><td className="mono">{p.id || p.planId}</td><td className="mono">{p.designId || '-'}</td><td><span className="badge badge-info">{p.status || 'DRAFT'}</span></td><td className="mono">{(p.checksum || '').slice(0, 12)}</td><td className="text-xs text-muted">{p.createdAt || '-'}</td></tr>
            ))}</tbody></table>
        )}
      </div>
    </div>
  );
}
