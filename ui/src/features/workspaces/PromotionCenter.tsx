
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function PromotionCenter() {
  const [promos, setPromos] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.promotions().then((d: any) => { setPromos(d.promotions || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  const badge = (s: string) => {
    const m: Record<string,string> = {APPROVED:'bg-green-100 text-green-700',PENDING_APPROVAL:'bg-yellow-100 text-yellow-700',CONSUMED:'bg-blue-100 text-blue-700',REJECTED:'bg-red-100 text-red-700'};
    return <span className={`px-2 py-0.5 rounded-full text-xs ${m[s]||'bg-gray-100 text-gray-600'}`}>{s}</span>;
  };

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Promotion Center</p>
        <h2 className="text-xl font-semibold text-gray-900">Environment Promotion</h2>
        <p className="text-sm text-gray-500 mt-1">SANDBOX → CONTROLLED_REAL → PRODUCTION. Promotion is NOT execution.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <div className="flex items-center justify-center gap-6 py-3">
          {['SANDBOX', 'CONTROLLED_REAL', 'PRODUCTION'].map((env, i) => (
            <div key={env} className="flex items-center gap-3">
              <div className="border border-gray-200 rounded-lg px-4 py-3 text-center">
                <p className="text-xs text-gray-400 mb-1">{env}</p>
                <span className={`px-2 py-0.5 rounded-full text-xs ${i===0?'bg-cyan-100 text-cyan-700':'bg-red-100 text-red-700'}`}>{i===0?'ASK':'BLOCK'}</span>
              </div>
              {i<2 && <span className="text-gray-300 text-lg">→</span>}
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Promotions</h3>
        {promos.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No promotions. Created after source environment verification completes.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">From</th><th className="pb-2 pr-4">To</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Req</th><th className="pb-2">Approved</th>
            </tr></thead>
            <tbody>
              {promos.map((p: any) => (
                <tr key={p.promotionId} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{p.promotionId}</td>
                  <td className="py-2 pr-4"><span className="px-2 py-0.5 rounded-full text-xs bg-cyan-100 text-cyan-700">{p.sourceEnvClass}</span></td>
                  <td className="py-2 pr-4"><span className={`px-2 py-0.5 rounded-full text-xs ${p.targetEnvClass==='PRODUCTION'?'bg-red-100 text-red-700':'bg-cyan-100 text-cyan-700'}`}>{p.targetEnvClass}</span></td>
                  <td className="py-2 pr-4">{badge(p.status)}</td>
                  <td className="py-2 pr-4 text-gray-600">{p.requestedBy||'-'}</td>
                  <td className="py-2 text-gray-600">{p.approvedBy||'-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
