
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function ProductionReadiness() {
  const [list, setList] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.readinessList().then((d: any) => { setList(d.readinessRecords || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;
  const latest = list[0];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Production Readiness</p>
        <h2 className="text-xl font-semibold text-gray-900">Production Eligibility</h2>
        <p className="text-sm text-gray-500 mt-1">Evaluates all gates. READY confirms eligibility only — PRODUCTION remains BLOCKED.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-8 text-center">
        <p className={`text-2xl font-bold ${latest?.readinessDecision==='READY'?'text-green-600':'text-red-600'}`}>
          {latest?.readinessDecision || 'NOT EVALUATED'}
        </p>
        <p className="text-sm text-gray-500 mt-2">Production Readiness Status</p>
        <div className="mt-4">
          <span className="px-3 py-1 rounded-full text-sm font-medium bg-red-100 text-red-700">PRODUCTION EXECUTION: BLOCKED</span>
        </div>
        <p className="text-xs text-gray-400 mt-3">Readiness confirms eligibility only. Future Production AIRLOCK required.</p>
      </div>

      {latest && (
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Gate Evaluation</h3>
          <div className="space-y-1">
            {(latest.blocks||[]).map((b:string) => (
              <div key={b} className="flex items-center gap-2 text-sm text-red-600 px-3 py-1.5 rounded bg-red-50">
                <span className="text-xs">✕</span> {b}
              </div>
            ))}
            {(latest.warnings||[]).map((w:string) => (
              <div key={w} className="flex items-center gap-2 text-sm text-yellow-600 px-3 py-1.5 rounded bg-yellow-50">
                <span className="text-xs">⚠</span> {w}
              </div>
            ))}
            {(!latest.blocks||latest.blocks.length===0) && (!latest.warnings||latest.warnings.length===0) && (
              <div className="flex items-center gap-2 text-sm text-green-600 px-3 py-1.5 rounded bg-green-50">
                <span className="text-xs">✓</span> All gates passed
              </div>
            )}
          </div>
        </div>
      )}

      {list.length === 0 && (
        <div className="bg-white border border-gray-200 rounded-lg p-10 text-center">
          <p className="text-sm text-gray-400">No readiness evaluation yet.</p>
          <p className="text-xs text-gray-400 mt-1">Evaluate with promotion, UAT, and rollback plan.</p>
        </div>
      )}
    </div>
  );
}
