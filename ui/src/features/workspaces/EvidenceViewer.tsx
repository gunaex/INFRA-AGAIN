
import { useState, useEffect } from 'react';
import { api } from '../../lib/api';

export default function EvidenceViewer() {
  const [runs, setRuns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.runs().then((d: any) => { setRuns(d.runs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <p className="text-gray-500 text-sm">Loading…</p>;
  const withEvidence = runs.filter((r: any) => r.evidence || r.verification);

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Evidence Viewer</p>
        <h2 className="text-xl font-semibold text-gray-900">Execution Evidence</h2>
        <p className="text-sm text-gray-500 mt-1">Before state, after state, observed state, validation, verification. Evidence is first-class.</p>
      </div>
      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Evidence Records</h3>
        {withEvidence.length === 0 ? (
          <p className="text-sm text-gray-400 py-8 text-center">No evidence records. Evidence is generated after execution and verification.</p>
        ) : (
          <div className="space-y-3">
            {withEvidence.map((r: any) => (
              <div key={r.runId || r.id} className="border border-gray-100 rounded-lg p-4">
                <div className="flex justify-between items-center mb-2">
                  <span className="font-mono text-xs text-gray-500">{r.runId || r.id}</span>
                  <span className="px-2 py-0.5 rounded-full text-xs bg-blue-100 text-blue-700">{r.status}</span>
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div>Validation: {r.validation?.result || '-'}</div>
                  <div>Verification: {r.verification?.result || '-'}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
