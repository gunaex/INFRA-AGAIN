
import React, { useState, useEffect } from 'react';
import { Cpu, Activity, Server } from 'lucide-react';
import { api } from '../../lib/api';

export default function ProviderIntelligence() {
  const [caps, setCaps] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    api.capabilities().then((d: any) => { setCaps(Array.isArray(d) ? d : []); setLoading(false); }).catch(() => setLoading(false));
  }, []);
  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;
  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Provider Intelligence</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Provider Capabilities</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>DISCOVERED ≠ SUPPORTED ≠ SAFE_TO_EXECUTE. Provider ≠ Platform.</div>
      </div>
      <div className="card">
        <div className="card-header"><div className="card-title">Providers</div></div>
        <div className="grid-2">
          {['AWS', 'GCP', 'ON_PREM', 'PRIVATE_CLOUD'].map(p => (
            <div key={p} className="card" style={{ borderColor: 'var(--border-default)' }}>
              <div className="flex-row gap-sm" style={{ marginBottom: 8 }}>
                <Cpu size={16} style={{ color: 'var(--text-muted)' }} />
                <span style={{ fontWeight: 600 }}>{p}</span>
              </div>
              <div className="text-xs text-muted">Real cloud validation: DEFERRED</div>
              <div className="badge badge-draft" style={{ marginTop: 8 }}>NOT EXECUTED</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
