
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function UatWorkspace() {
  const [uats, setUats] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.uats().then((d: any) => { setUats(d.uats || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">UAT Workspace</p>
        <h2 className="text-xl font-semibold text-gray-900">User Acceptance Testing</h2>
        <p className="text-sm text-gray-500 mt-1">Production eligibility requires UAT PASSED + separation of duties.</p>
      </div>
      <div className="border border-yellow-200 bg-yellow-50 rounded-lg p-4 text-sm">
        <p className="font-medium text-yellow-800">Separation of Duties</p>
        <p className="text-yellow-700 text-xs mt-1">Performer ≠ Approver. UAT after PASS is immutable — mutation invalidates.</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">UAT Records</h3>
        {uats.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No UAT records. Create with scope, criteria, and separation of duties.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Performed By</th><th className="pb-2 pr-4">Approved By</th><th className="pb-2">Completed</th>
            </tr></thead>
            <tbody>
              {uats.map((u: any) => (
                <tr key={u.uatId} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{u.uatId}</td>
                  <td className="py-2 pr-4"><span className={`px-2 py-0.5 rounded-full text-xs ${u.status==='PASSED'?'bg-green-100 text-green-700':u.status==='FAILED'?'bg-red-100 text-red-700':'bg-gray-100 text-gray-600'}`}>{u.status}</span></td>
                  <td className="py-2 pr-4 text-gray-600">{u.performedBy||'-'}</td>
                  <td className="py-2 pr-4 text-gray-600">{u.approvedBy||'-'}</td>
                  <td className="py-2 text-xs text-gray-400">{u.completedAt||'-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
