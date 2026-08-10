
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function ArchitectureWorkspace() {
  const [designs, setDesigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.designs().then((d: any) => { setDesigns(d.designs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Architecture Workspace</p>
        <h2 className="text-xl font-semibold text-gray-900">Infrastructure Design</h2>
        <p className="text-sm text-gray-500 mt-1">Provider-neutral architecture modeling. Provider ≠ Platform.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Providers</h3>
          <div className="space-y-2">
            {['AWS', 'GCP', 'ON_PREM', 'PRIVATE_CLOUD'].map(p => (
              <div key={p} className="flex justify-between text-sm">
                <span className="text-gray-700">{p}</span>
                <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">NOT EXECUTED</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white border border-gray-200 rounded-lg p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">Platforms</h3>
          <div className="space-y-2">
            {['NATIVE_VM', 'KUBERNETES', 'OPENSHIFT_OCP', 'BARE_METAL'].map(p => (
              <div key={p} className="flex justify-between text-sm">
                <span className="text-gray-700">{p}</span>
                <span className="text-xs text-gray-400">{p === 'OPENSHIFT_OCP' ? 'Platform (not provider)' : ''}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Designs</h3>
        {designs.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No designs yet. Create an architecture design to define infrastructure topology.</p>
        ) : (
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-100 text-left text-xs text-gray-400 uppercase tracking-wider">
              <th className="pb-2 pr-4">ID</th><th className="pb-2 pr-4">Status</th><th className="pb-2 pr-4">Provider</th><th className="pb-2">Created</th>
            </tr></thead>
            <tbody>
              {designs.map((d: any) => (
                <tr key={d.id || d.designId} className="border-b border-gray-50">
                  <td className="py-2 pr-4 font-mono text-xs text-gray-500">{d.id || d.designId}</td>
                  <td className="py-2 pr-4"><span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">{d.status || 'DRAFT'}</span></td>
                  <td className="py-2 pr-4 text-gray-600">{d.provider || '-'}</td>
                  <td className="py-2 text-xs text-gray-400">{d.createdAt || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
