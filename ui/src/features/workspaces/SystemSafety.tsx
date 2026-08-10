
import React from 'react';
import { Shield, Activity, Lock, FileCheck, Eye, Key } from 'lucide-react';

export default function SystemSafety() {
  const safetyItems = [
    { label: 'AdminAuth', desc: 'Argon2id/PBKDF2 password verification, max 3 attempts', icon: Key, status: 'IMPLEMENTED' },
    { label: 'Immutable Approval', desc: 'SHA256 canonical digest, seal/verify/save/load', icon: FileCheck, status: 'IMPLEMENTED' },
    { label: 'AIRLOCK', desc: 'State machine: DISCOVERY → AIRLOCK_PASSED → EXECUTING', icon: Lock, status: 'IMPLEMENTED' },
    { label: 'Guarded Mutator', desc: 'Every S3 mutation asserts airlock first', icon: Shield, status: 'IMPLEMENTED' },
    { label: 'Ownership Enforcement', desc: 'Exact resource ownership, no prefix delete, no wildcard', icon: Eye, status: 'IMPLEMENTED' },
  ];

  const ladder = [
    { level: 'PLAN_ONLY', policy: 'AUTO' },
    { level: 'SIMULATED', policy: 'AUTO' },
    { level: 'LOCAL_RUNTIME', policy: 'AUTO (isolated)' },
    { level: 'LOCAL_PRIVATE_CLOUD', policy: 'ASK' },
    { level: 'SANDBOX', policy: 'ASK' },
    { level: 'CONTROLLED_REAL', policy: 'BLOCK' },
    { level: 'PRODUCTION', policy: 'BLOCK' },
  ];

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>System Safety</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Safety Controls</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Real cloud execution has NOT been performed. All safety belts are source-level verified.</div>
      </div>

      {/* Safety Ladder */}
      <div className="card" style={{ marginBottom: 24 }}>
        <div className="card-title" style={{ marginBottom: 16 }}>Safety Ladder</div>
        <div className="flex-col gap-sm">
          {ladder.map(s => (
            <div key={s.level} className="flex-between" style={{ padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: s.policy === 'BLOCK' ? 'var(--status-blocked-bg)' : s.policy === 'ASK' ? 'var(--status-ask-bg)' : 'transparent' }}>
              <span className="text-sm">{s.level}</span>
              <span className={`badge ${s.policy === 'BLOCK' ? 'badge-blocked' : s.policy === 'ASK' ? 'badge-ask' : 'badge-info'}`}>{s.policy}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Safety Belt Components */}
      <div className="card">
        <div className="card-title" style={{ marginBottom: 16 }}>Safety Belt Components</div>
        <div className="flex-col gap-sm">
          {safetyItems.map(s => {
            const Icon = s.icon;
            return (
              <div key={s.label} className="flex-row gap-md" style={{ padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-elevated)' }}>
                <Icon size={16} style={{ color: 'var(--status-info)', flexShrink: 0 }} />
                <div>
                  <div className="text-sm" style={{ fontWeight: 600 }}>{s.label}</div>
                  <div className="text-xs text-muted">{s.desc}</div>
                </div>
                <span className="badge badge-verified" style={{ marginLeft: 'auto' }}>{s.status}</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Real Cloud Status */}
      <div className="card" style={{ marginTop: 24, borderColor: 'var(--border-default)' }}>
        <div className="flex-row gap-md">
          <Activity size={16} style={{ color: 'var(--text-muted)' }} />
          <div>
            <div className="text-sm" style={{ fontWeight: 600 }}>Real Cloud Validation</div>
            <div className="text-xs text-muted">DEFERRED. No AWS credentials configured. No real S3 operations performed. Implementation completeness does NOT imply real-cloud certification.</div>
          </div>
          <span className="badge badge-draft">DEFERRED</span>
        </div>
      </div>
    </div>
  );
}
