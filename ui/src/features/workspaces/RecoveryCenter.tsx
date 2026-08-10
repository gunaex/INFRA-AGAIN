
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function RecoveryCenter() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.rollbackPlans().then((d: any) => { setPlans(d.rollbackPlans || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Recovery Center</p>
        <h2 className="text-xl font-semibold text-gray-900">Rollback & Recovery</h2>
        <p className="text-sm text-gray-500 mt-1">Rollback executor success ≠ Recovery verified. Unknown state never equals SUCCESS.</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Rollback Plans</h3>
        {plans.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No rollback plans. Define plans with trigger conditions, recovery steps, and verification.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Owner</th><th className="pb-2 pr-4">Recovery State</th><th className="pb-2">Max Duration</th>
            </tr></thead>
            <tbody>
              {plans.map((p: any) => (
                <tr key={p.rollbackId} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{p.rollbackId}</td>
                  <td className="py-2 pr-4"><span className={`px-2 py-0.5 rounded-full text-xs ${p.status==='APPROVED'?'bg-green-100 text-green-700':'bg-gray-100 text-gray-600'}`}>{p.status}</span></td>
                  <td className="py-2 pr-4 text-gray-600">{p.owner||'-'}</td>
                  <td className="py-2 pr-4 text-gray-600">{p.expectedRecoveryState||'-'}</td>
                  <td className="py-2 text-gray-600">{p.maxDurationSeconds}s</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
