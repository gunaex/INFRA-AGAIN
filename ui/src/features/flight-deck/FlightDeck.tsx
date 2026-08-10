import React, { useState, useEffect } from 'react';
import {
  Activity, ArrowRight, Shield, AlertTriangle, CheckCircle2,
  Clock, Users, FileText, Play, FileSearch, ArrowUpRight,
  RotateCcw, ClipboardCheck, Box
} from 'lucide-react';
import { api } from '../../lib/api';

interface Props { onNavigate: (v: any) => void; }

export default function FlightDeck({ onNavigate }: Props) {
  const [envs, setEnvs] = useState<any[]>([]);
  const [promos, setPromos] = useState<any[]>([]);
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.environments().catch(() => ({ environments: [] })),
      api.promotions().catch(() => ({ promotions: [] })),
      api.runs().catch(() => ({ runs: [] })),
    ]).then(([e, p, r]) => {
      setEnvs(e.environments || []);
      setPromos(p.promotions || []);
      setRuns(r.runs || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;

  const sb = envs.find((e: any) => e.classification === 'SANDBOX');
  const cr = envs.find((e: any) => e.classification === 'CONTROLLED_REAL');
  const prod = envs.find((e: any) => e.classification === 'PRODUCTION');
  const approvedPromos = promos.filter((p: any) => p.status === 'APPROVED');
  const pendingPromos = promos.filter((p: any) => p.status === 'PENDING_APPROVAL');

  // Determine lifecycle state
  const hasDesign = runs.length > 0;
  const hasPlan = promos.length > 0;
  const hasExecution = runs.some((r: any) => r.status === 'COMPLETED');
  const hasVerification = runs.some((r: any) => r.verification?.result === 'PASS');
  const hasPromotion = approvedPromos.length > 0;

  type StageState = 'complete' | 'active' | 'blocked' | 'ask' | undefined;
  const stages: { label: string; state: StageState }[] = [
    { label: 'Design', state: hasDesign ? 'complete' : 'active' },
    { label: 'Plan', state: hasPlan ? 'complete' : undefined },
    { label: 'Execute', state: hasExecution ? 'complete' : hasPlan ? 'active' : undefined },
    { label: 'Observe', state: hasExecution ? 'complete' : undefined },
    { label: 'Validate', state: hasExecution ? 'complete' : undefined },
    { label: 'Verify', state: hasVerification ? 'complete' : undefined },
    { label: 'Evidence', state: hasVerification ? 'complete' : undefined },
    { label: 'Promote', state: hasPromotion ? 'complete' : hasVerification ? 'active' : undefined },
  ];

  // Next action
  let nextAction = 'Create an Architecture Design to begin';
  let nextView: any = 'architecture';
  if (hasDesign && !hasPlan) { nextAction = 'Implementation Plan requires approval'; nextView = 'implementation'; }
  else if (hasPlan && !hasExecution) { nextAction = 'Execution package ready for AIRLOCK'; nextView = 'execution'; }
  else if (hasExecution && !hasVerification) { nextAction = 'Verification evidence ready for review'; nextView = 'evidence'; }
  else if (hasVerification && !hasPromotion) { nextAction = 'Promotion pending approval'; nextView = 'promotion'; }
  else if (pendingPromos.length > 0) { nextAction = `${pendingPromos.length} promotion(s) awaiting approval`; nextView = 'promotion'; }
  else if (hasPromotion) { nextAction = 'Production readiness evaluation available'; nextView = 'production-readiness'; }

  return (
    <div>
      {/* Hero */}
      <div style={{ marginBottom: 32 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 8 }}>
          Infrastructure Flight Deck
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          INFRA-AGAIN
        </div>
        <div className="text-secondary" style={{ fontSize: 14, maxWidth: 600 }}>
          Infrastructure control center — Design, Plan, Execute, Verify, Promote.
          Every stage independently validated. No single observer defines success.
        </div>
      </div>

      {/* Environment cards */}
      <div className="grid-3" style={{ marginBottom: 24 }}>
        {[sb, cr, prod].map((env: any) => {
          if (!env) return null;
          const isProd = env.classification === 'PRODUCTION';
          const isCR = env.classification === 'CONTROLLED_REAL';
          const badgeCls = isProd || isCR ? 'badge-blocked' : 'badge-info';
          const badgeText = isProd || isCR ? 'BLOCKED' : 'ASK';
          return (
            <div key={env.environmentId} className="card">
              <div className="flex-between" style={{ marginBottom: 12 }}>
                <div className="card-title">{env.name || env.classification}</div>
                <span className={`badge ${badgeCls}`}>{badgeText}</span>
              </div>
              <div className="flex-col gap-xs text-sm text-secondary">
                <div className="flex-row gap-sm">
                  <Box size={12} /><span>{env.provider?.toUpperCase() || 'AWS'}</span>
                </div>
                <div className="flex-row gap-sm">
                  <Activity size={12} /><span>{env.region || 'us-east-1'}</span>
                </div>
                <div className="flex-row gap-sm">
                  <Shield size={12} /><span>Blast Radius: {env.blastRadius || 'N/A'}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Lifecycle Pipeline */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 16 }}>Lifecycle State</div>
        <div className="pipeline">
          {stages.map((s, i) => (
            <React.Fragment key={s.label}>
              {i > 0 && <div className={`pipeline-line${s.state === 'complete' ? ' complete' : ''}`} />}
              <div className="pipeline-stage">
                <div className={`pipeline-dot${s.state ? ` ${s.state}` : ''}`} />
                <div className={`pipeline-label${s.state === 'active' ? ' active' : ''}`}>{s.label}</div>
              </div>
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Next Action + Stats */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div className="card" style={{ cursor: 'pointer' }} onClick={() => onNavigate(nextView)}>
          <div className="card-subtitle" style={{ marginBottom: 8 }}>NEXT ACTION</div>
          <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--status-info)', marginBottom: 8 }}>
            {nextAction}
          </div>
          <div className="flex-row gap-xs text-sm" style={{ color: 'var(--status-info)' }}>
            <ArrowRight size={14} /> Go to {NAV_LABELS[nextView] || 'workspace'}
          </div>
        </div>

        <div className="card">
          <div className="card-subtitle" style={{ marginBottom: 12 }}>SYSTEM SAFETY</div>
          <div className="flex-col gap-sm">
            {[
              { label: 'SANDBOX', status: 'ASK', cls: 'badge-info' },
              { label: 'CONTROLLED REAL', status: 'BLOCK', cls: 'badge-blocked' },
              { label: 'PRODUCTION', status: 'BLOCK', cls: 'badge-blocked' },
            ].map(s => (
              <div key={s.label} className="flex-between">
                <span className="text-sm text-secondary">{s.label}</span>
                <span className={`badge ${s.cls}`}>{s.status}</span>
              </div>
            ))}
            <div className="divider" style={{ margin: '4px 0' }} />
            <div className="flex-between">
              <span className="text-sm text-secondary">REAL CLOUD VALIDATION</span>
              <span className="badge badge-draft">DEFERRED</span>
            </div>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid-4">
        <div className="card">
          <div className="metric-value">{promos.length}</div>
          <div className="metric-label">Promotions</div>
          {pendingPromos.length > 0 && (
            <div className="text-sm" style={{ color: 'var(--status-ask)', marginTop: 4 }}>
              {pendingPromos.length} pending
            </div>
          )}
        </div>
        <div className="card">
          <div className="metric-value">{runs.length}</div>
          <div className="metric-label">Execution Runs</div>
        </div>
        <div className="card">
          <div className="metric-value">{envs.length}</div>
          <div className="metric-label">Environments</div>
        </div>
        <div className="card">
          <div className="metric-value">{approvedPromos.length}</div>
          <div className="metric-label">Approved</div>
        </div>
      </div>

      {/* Recent Promotions */}
      {promos.length > 0 && (
        <>
          <div className="section-title" style={{ marginTop: 32 }}>Recent Promotions</div>
          <div className="card">
            <table className="table-compact">
              <thead><tr>
                <th>ID</th><th>Source</th><th>Target</th><th>Status</th><th>Requested By</th>
              </tr></thead>
              <tbody>
                {promos.slice(0, 5).map((p: any) => (
                  <tr key={p.promotionId} style={{ cursor: 'pointer' }} onClick={() => onNavigate('promotion')}>
                    <td className="mono">{p.promotionId}</td>
                    <td>{p.sourceEnvClass}</td>
                    <td>{p.targetEnvClass}</td>
                    <td><span className={`badge badge-${p.status === 'APPROVED' ? 'verified' : p.status === 'PENDING_APPROVAL' ? 'ask' : p.status === 'CONSUMED' ? 'info' : 'draft'}`}>{p.status}</span></td>
                    <td>{p.requestedBy || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Empty state for new installations */}
      {promos.length === 0 && runs.length === 0 && (
        <div className="card" style={{ marginTop: 24 }}>
          <div className="empty-state">
            <Activity size={32} className="empty-state-icon" />
            <div className="empty-state-title">No infrastructure activity yet</div>
            <div className="empty-state-desc">
              Start by creating an architecture design, then follow the lifecycle through planning, execution, verification, and promotion.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const NAV_LABELS: Record<string, string> = {
  architecture: 'Architecture',
  implementation: 'Implementation',
  execution: 'Execution',
  evidence: 'Evidence',
  promotion: 'Promotion',
  'production-readiness': 'Production Readiness',
};
