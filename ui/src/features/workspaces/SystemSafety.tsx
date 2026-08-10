
export default function SystemSafety() {
  const ladder = [
    { level: 'PLAN_ONLY', policy: 'AUTO', blocked: false },
    { level: 'SIMULATED', policy: 'AUTO', blocked: false },
    { level: 'LOCAL_RUNTIME', policy: 'AUTO (isolated)', blocked: false },
    { level: 'LOCAL_PRIVATE_CLOUD', policy: 'ASK', blocked: false },
    { level: 'SANDBOX', policy: 'ASK', blocked: false },
    { level: 'CONTROLLED_REAL', policy: 'BLOCK', blocked: true },
    { level: 'PRODUCTION', policy: 'BLOCK', blocked: true },
  ];

  const belts = [
    { label: 'AdminAuth', desc: 'Argon2id/PBKDF2 password verification, max 3 attempts' },
    { label: 'Immutable Approval', desc: 'SHA256 canonical digest, seal/verify/save/load' },
    { label: 'AIRLOCK', desc: 'State machine: DISCOVERY → AIRLOCK_PASSED → EXECUTING' },
    { label: 'Guarded Mutator', desc: 'Every S3 mutation asserts airlock first' },
    { label: 'Ownership Enforcement', desc: 'Exact resource ownership, no prefix delete' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">System Safety</p>
        <h2 className="text-xl font-semibold text-gray-900">Safety Controls</h2>
        <p className="text-sm text-gray-500 mt-1">Real cloud execution has NOT been performed. All safety belts are source-level verified.</p>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Safety Ladder</h3>
        <div className="space-y-1">
          {ladder.map(s => (
            <div key={s.level} className={`flex justify-between px-3 py-2 rounded text-sm ${s.blocked ? 'bg-red-50' : 'bg-gray-50'}`}>
              <span className="text-gray-700">{s.level}</span>
              <span className={`px-2 py-0.5 rounded-full text-xs ${s.blocked ? 'bg-red-100 text-red-700' : s.policy==='ASK' ? 'bg-yellow-100 text-yellow-700' : 'bg-cyan-100 text-cyan-700'}`}>{s.policy}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white border border-gray-200 rounded-lg p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">Safety Belt Components</h3>
        <div className="space-y-2">
          {belts.map(b => (
            <div key={b.label} className="flex justify-between items-center px-3 py-2 rounded bg-gray-50 text-sm">
              <div>
                <p className="font-medium text-gray-700">{b.label}</p>
                <p className="text-xs text-gray-400">{b.desc}</p>
              </div>
              <span className="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">IMPLEMENTED</span>
            </div>
          ))}
        </div>
      </div>

      <div className="border border-gray-200 bg-white rounded-lg p-5 flex items-center gap-4">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-700">Real Cloud Validation</p>
          <p className="text-xs text-gray-400 mt-1">DEFERRED. No AWS credentials configured. No real S3 operations performed.</p>
        </div>
        <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">DEFERRED</span>
      </div>
    </div>
  );
}
