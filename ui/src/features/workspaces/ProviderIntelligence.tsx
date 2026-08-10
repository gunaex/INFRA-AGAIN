
export default function ProviderIntelligence() {
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs text-gray-400 uppercase tracking-wide">Provider Intelligence</p>
        <h2 className="text-xl font-semibold text-gray-900">Provider Capabilities</h2>
        <p className="text-sm text-gray-500 mt-1">DISCOVERED ≠ SUPPORTED ≠ SAFE_TO_EXECUTE. Provider ≠ Platform.</p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {['AWS', 'GCP', 'ON_PREM', 'PRIVATE_CLOUD'].map(p => (
          <div key={p} className="bg-white border border-gray-200 rounded-lg p-5">
            <h3 className="font-semibold text-gray-900 mb-2">{p}</h3>
            <p className="text-xs text-gray-400 mb-3">Real cloud validation: DEFERRED</p>
            <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-500">NOT EXECUTED</span>
          </div>
        ))}
      </div>
    </div>
  );
}
