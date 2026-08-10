
import React, { useState, useEffect } from 'react';
import { ArrowUpRight, Activity, Shield, CheckCircle2, AlertTriangle, Clock } from 'lucide-react';
import { api } from '../../lib/api';

export default function PromotionCenter() {
  const [promos, setPromos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const load = () => {
    api.promotions().then((d: any) => { setPromos(d.promotions || []); setLoading(false); }).catch(() => setLoading(false));
  };
  useEffect(() => { load(); }, []);

  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Promotion Center</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Environment Promotion</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>
          SANDBOX → CONTROLLED_REAL → PRODUCTION. Promotion is NOT execution.
        </div>
      </div>

      {/* Transition Flow */}
      <div className="card" style={{ marginBottom: 24, textAlign: 'center' }}>
        <div className="flex-row" style={{ justifyContent: 'center', gap: 32, padding: '16px 0' }}>
          {['SANDBOX', 'CONTROLLED_REAL', 'PRODUCTION'].map((env, i) => (
            <React.Fragment key={env}>
              <div className="card" style={{ minWidth: 140, textAlign: 'center' }}>
                <div className="text-xs text-muted" style={{ marginBottom: 4 }}>{env}</div>
                <span className={`badge ${env === 'SANDBOX' ? 'badge-info' : 'badge-blocked'}`}>
                  {env === 'SANDBOX' ? 'ASK' : 'BLOCK'}
                </span>
              </div>
              {i < 2 && <ArrowUpRight size={20} style={{ color: 'var(--text-muted)' }} />}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Promotions Table */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Promotions</div>
        </div>
        {promos.length === 0 ? (
          <div className="empty-state">
            <ArrowUpRight size={24} className="empty-state-icon" />
            <div className="empty-state-title">No promotions</div>
            <div className="empty-state-desc">Promotions are created after source environment verification is complete.</div>
          </div>
        ) : (
          <table className="table-compact">
            <thead><tr><th>ID</th><th>Source</th><th>Target</th><th>Status</th><th>Requested</th><th>Approved</th><th>Digest</th></tr></thead>
            <tbody>
              {promos.map((p: any) => (
                <tr key={p.promotionId}>
                  <td className="mono">{p.promotionId}</td>
                  <td><span className="badge badge-info">{p.sourceEnvClass}</span></td>
                  <td><span className={`badge ${p.targetEnvClass === 'PRODUCTION' ? 'badge-blocked' : 'badge-info'}`}>{p.targetEnvClass}</span></td>
                  <td><span className={`badge ${p.status === 'APPROVED' ? 'badge-verified' : p.status === 'PENDING_APPROVAL' ? 'badge-ask' : p.status === 'CONSUMED' ? 'badge-info' : p.status === 'REJECTED' ? 'badge-failure' : 'badge-draft'}`}>{p.status}</span></td>
                  <td>{p.requestedBy || '-'}</td>
                  <td>{p.approvedBy || '-'}</td>
                  <td className="mono">{(p.promotionDigest || '').slice(0, 12)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
