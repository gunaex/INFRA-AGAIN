
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function ImplementationWorkspace() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.implementationPlans().then((d: any) => { setPlans(d.plans || d.implementation_plans || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Implementation Workspace</p>
        <h2 className="text-xl font-semibold text-gray-900">Implementation Plans</h2>
        <p className="text-sm text-gray-500 mt-1">From architecture design to executable plan. Baseline frozen before execution.</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Plans</h3>
        {plans.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No implementation plans. Create a plan from an accepted architecture design.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">Plan ID</th><th className="pb-2 pr-4">Design ID</th><th className="pb-2 pr-4">Status</th><th className="pb-2">Checksum</th>
            </tr></thead>
            <tbody>
              {plans.map((p: any) => (
                <tr key={p.id || p.planId} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{p.id || p.planId}</td>
                  <td className="py-2 pr-4 font-mono text-xs text-gray-400">{p.designId || '-'}</td>
                  <td className="py-2 pr-4"><span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">{p.status || 'DRAFT'}</span></td>
                  <td className="py-2 font-mono text-xs text-gray-400">{(p.checksum || '').slice(0, 12)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
