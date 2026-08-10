import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    APPROVED: 'bg-green-100 text-green-700',
    PENDING_APPROVAL: 'bg-yellow-100 text-yellow-700',
    CONSUMED: 'bg-blue-100 text-blue-700',
    REJECTED: 'bg-red-100 text-red-700',
    DRAFT: 'bg-gray-100 text-gray-600',
    PASSED: 'bg-green-100 text-green-700',
    FAILED: 'bg-red-100 text-red-700',
    NOT_STARTED: 'bg-gray-100 text-gray-600',
    ASK: 'bg-cyan-100 text-cyan-700',
    BLOCK: 'bg-red-100 text-red-700',
    BLOCKED: 'bg-red-100 text-red-700',
    DEFERRED: 'bg-gray-100 text-gray-500',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs ${styles[status] || 'bg-gray-100 text-gray-600'}`}>
      {status}
    </span>
  );
}

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

  if (loading) return <p className="text-gray-500 text-sm">Loading\u2026</p>;

  const sb = envs.find((e: any) => e.classification === 'SANDBOX');
  const cr = envs.find((e: any) => e.classification === 'CONTROLLED_REAL');
  const prod = envs.find((e: any) => e.classification === 'PRODUCTION');
  const approvedPromos = promos.filter((p: any) => p.status === 'APPROVED');
  const pendingPromos = promos.filter((p: any) => p.status === 'PENDING_APPROVAL');

  const hasExecution = runs.some((r: any) => r.status === 'COMPLETED');
  const hasPromotion = approvedPromos.length > 0;

  let nextAction = 'Create an Architecture Design to begin';
  let nextView: any = 'architecture';
  if (hasExecution && !hasPromotion) { nextAction = 'Promotion pending approval'; nextView = 'promotion'; }
  else if (pendingPromos.length > 0) { nextAction = `${pendingPromos.length} promotion(s) awaiting approval`; nextView = 'promotion'; }
  else if (hasPromotion) { nextAction = 'Production readiness evaluation available'; nextView = 'production-readiness'; }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Infrastructure Flight Deck</p>
        <h2 className="text-xl font-semibold text-gray-900">INFRA-AGAIN</h2>
        <p className="text-sm text-gray-500 mt-1 max-w-2xl">
          Infrastructure control center — Design, Plan, Execute, Verify, Promote. Every stage independently validated. No single observer defines success.
        </p>
      </div>

      {/* Environment cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[sb, cr, prod].map((env: any) => {
          if (!env) return null;
          const isBlocked = env.classification === 'PRODUCTION' || env.classification === 'CONTROLLED_REAL';
          return (
            <div key={env.environmentId} className="bg-white border border-gray-200 rounded-lg p-5">
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-medium text-gray-900 text-sm">{env.name || env.classification}</h3>
                <StatusBadge status={isBlocked ? 'BLOCK' : 'ASK'} />
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>{env.provider?.toUpperCase() || 'AWS'} · {env.region || 'us-east-1'}</div>
                <div>Blast Radius: {env.blastRadius || 'N/A'}</div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Lifecycle Pipeline */}
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Lifecycle State</h3>
        <div className="flex items-center gap-0 overflow-x-auto">
          {['Design', 'Plan', 'Execute', 'Observe', 'Validate', 'Verify', 'Evidence', 'Promote'].map((s, i) => {
            const done = i < (hasPromotion ? 8 : hasExecution ? 3 : 0);
            return (
              <div key={s} className="flex items-center">
                {i > 0 && <div className={`w-8 h-0.5 ${done ? 'bg-green-500' : 'bg-gray-200'}`} />}
                <div className="flex flex-col items-center min-w-[64px]">
                  <div className={`w-3 h-3 rounded-full border-2 ${done ? 'bg-green-500 border-green-500' : 'border-gray-300'}`} />
                  <span className={`text-[9px] uppercase tracking-wider mt-1 ${done ? 'text-gray-700' : 'text-gray-400'}`}>{s}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Next Action + Safety */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <button onClick={() => onNavigate(nextView)} className="text-left bg-white border border-gray-200 rounded-lg p-5 hover:border-cyan-300 hover:shadow-md transition">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-1">NEXT ACTION</p>
          <p className="text-sm font-medium text-cyan-700">{nextAction}</p>
          <p className="text-xs text-cyan-600 mt-2">Go to workspace \u2192</p>
        </button>
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <p className="text-xs text-gray-400 uppercase tracking-wide mb-3">SYSTEM SAFETY</p>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-gray-600">SANDBOX</span><StatusBadge status="ASK" /></div>
            <div className="flex justify-between"><span className="text-gray-600">CONTROLLED REAL</span><StatusBadge status="BLOCK" /></div>
            <div className="flex justify-between"><span className="text-gray-600">PRODUCTION</span><StatusBadge status="BLOCK" /></div>
            <div className="border-t border-gray-100 pt-2 flex justify-between"><span className="text-gray-600">REAL CLOUD VALIDATION</span><StatusBadge status="DEFERRED" /></div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { value: promos.length, label: 'Promotions', sub: pendingPromos.length > 0 ? `${pendingPromos.length} pending` : '' },
          { value: runs.length, label: 'Execution Runs', sub: '' },
          { value: envs.length, label: 'Environments', sub: '' },
          { value: approvedPromos.length, label: 'Approved', sub: '' },
        ].map(s => (
          <div key={s.label} className="bg-white border border-gray-200 rounded-lg p-4">
            <p className="text-2xl font-semibold text-gray-900">{s.value}</p>
            <p className="text-xs text-gray-500 uppercase">{s.label}</p>
            {s.sub && <p className="text-xs text-yellow-600 mt-1">{s.sub}</p>}
          </div>
        ))}
      </div>

      {/* Empty state */}
      {promos.length === 0 && runs.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-10 text-center">
          <p className="text-gray-400 text-sm">No infrastructure activity yet.</p>
          <p className="text-xs text-gray-400 mt-1">Start by creating an architecture design.</p>
        </div>
      )}
    </div>
  );
}
