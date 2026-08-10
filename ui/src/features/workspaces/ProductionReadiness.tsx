
import React, { useState, useEffect } from 'react';
import { CheckCircle2, Activity, Shield, XCircle, AlertTriangle } from 'lucide-react';
import { api } from '../../lib/api';

export default function ProductionReadiness() {
  const [readiness, setReadiness] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.readinessList().then((d: any) => { setReadiness(d.readinessRecords || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  const latest = readiness[0];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Production Readiness</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Production Eligibility</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Evaluates all gates. READY confirms eligibility only — PRODUCTION remains BLOCKED.</div>
      </div>

      {/* State Banner */}
      <div className="card" style={{ marginBottom: 24, textAlign: 'center', padding: 32 }}>
        <CheckCircle2 size={32} style={{ color: latest?.readinessDecision === 'READY' ? 'var(--status-verified)' : 'var(--status-blocked)', marginBottom: 12 }} />
        <div style={{ fontSize: 24, fontWeight: 700, color: latest?.readinessDecision === 'READY' ? 'var(--status-verified)' : 'var(--status-blocked)' }}>
          {latest?.readinessDecision || 'NOT EVALUATED'}
        </div>
        <div className="text-sm text-secondary" style={{ marginTop: 8 }}>Production Readiness Status</div>
        <div style={{ marginTop: 16 }}>
          <span className="badge badge-blocked" style={{ fontSize: 12, padding: '4px 16px' }}>
            PRODUCTION EXECUTION: BLOCKED
          </span>
        </div>
        <div className="text-xs text-muted" style={{ marginTop: 8 }}>Readiness confirms eligibility only. Explicit future Production AIRLOCK is still required.</div>
      </div>

      {/* Blockers Checklist */}
      {latest && (
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>Gate Evaluation</div>
          <div className="checklist">
            {(latest.blocks || []).map((b: string) => (
              <div key={b} className="checklist-item fail">
                <XCircle size={14} /> {b}
              </div>
            ))}
            {(latest.warnings || []).map((w: string) => (
              <div key={w} className="checklist-item warn">
                <AlertTriangle size={14} /> {w}
              </div>
            ))}
            {(!latest.blocks || latest.blocks.length === 0) && (!latest.warnings || latest.warnings.length === 0) && (
              <div className="checklist-item pass"><CheckCircle2 size={14} /> All gates passed</div>
            )}
          </div>
        </div>
      )}

      {readiness.length === 0 && (
        <div className="card">
          <div className="empty-state"><Shield size={24} className="empty-state-icon" /><div className="empty-state-title">No readiness evaluation</div><div className="empty-state-desc">Evaluate production readiness with promotion, UAT, and rollback plan to see gate results.</div></div>
        </div>
      )}
    </div>
  );
}
