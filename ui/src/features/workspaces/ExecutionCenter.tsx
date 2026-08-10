
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function ExecutionCenter() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.runs().then((d: any) => { setRuns(d.runs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Execution Center</p>
        <h2 className="text-xl font-semibold text-gray-900">Execution & Verification</h2>
        <p className="text-sm text-gray-500 mt-1">Executor Success ≠ Verified Success. Every stage independently validated.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Execution Pipeline</h3>
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-3">
          {['PLAN', 'EXECUTOR', 'OBSERVER', 'VALIDATOR', 'VERIFIER', 'EVIDENCE'].map(s => (
            <div key={s} className="border border-gray-200 rounded-lg p-3 text-center">
              <p className="text-xs text-gray-400 uppercase tracking-wide">{s}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Execution Runs</h3>
        {runs.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No execution runs. Execute an approved plan to see results.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">Run ID</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Validation</th><th className="pb-2">Fidelity</th>
            </tr></thead>
            <tbody>
              {runs.map((r: any) => (
                <tr key={r.runId || r.id} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{r.runId || r.id}</td>
                  <td className="py-2 pr-4"><span className={`px-2 py-0.5 rounded-full text-xs ${r.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 'bg-blue-100 text-blue-700'}`}>{r.status}</span></td>
                  <td className="py-2 pr-4 text-gray-600">{r.validation?.result || '-'}</td>
                  <td className="py-2"><span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">{r.fidelity || '-'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
