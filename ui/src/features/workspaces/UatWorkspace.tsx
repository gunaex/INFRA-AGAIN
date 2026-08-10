
import React, { useState, useEffect } from 'react';
import { ClipboardCheck, Activity, Users } from 'lucide-react';
import { api } from '../../lib/api';

export default function UatWorkspace() {
  const [uats, setUats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.uats().then((d: any) => { setUats(d.uats || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>UAT Workspace</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>User Acceptance Testing</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Production eligibility requires UAT PASSED + separation of duties.</div>
      </div>
      {/* SoD notice */}
      <div className="card" style={{ marginBottom: 24, borderColor: 'var(--status-ask)', background: 'var(--status-ask-bg)' }}>
        <div className="flex-row gap-sm">
          <Users size={16} style={{ color: 'var(--status-ask)' }} />
          <div>
            <div className="text-sm" style={{ fontWeight: 600 }}>Separation of Duties</div>
            <div className="text-xs text-secondary">Performer ≠ Approver. UAT PASSED after PASS is immutable — mutation invalidates.</div>
          </div>
        </div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">UAT Records</div></div>
        {uats.length === 0 ? (
          <div className="empty-state"><ClipboardCheck size={24} className="empty-state-icon" /><div className="empty-state-title">No UAT records</div><div className="empty-state-desc">Create UAT records with scope, acceptance criteria, and separation of duties.</div></div>
        ) : (
          <table className="table-compact"><thead><tr><th>ID</th><th>Status</th><th>Performed By</th><th>Approved By</th><th>Completed</th></tr></thead><tbody>
            {uats.map((u: any) => (
              <tr key={u.uatId}><td className="mono">{u.uatId}</td><td><span className={`badge ${u.status === 'PASSED' ? 'badge-verified' : u.status === 'FAILED' ? 'badge-failure' : 'badge-draft'}`}>{u.status}</span></td><td>{u.performedBy || '-'}</td><td>{u.approvedBy || '-'}</td><td className="text-xs text-muted">{u.completedAt || '-'}</td></tr>
            ))}</tbody></table>
        )}
      </div>
    </div>
  );
}
