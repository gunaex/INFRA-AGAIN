import React, { useState, useEffect } from 'react';
import { Box, Cpu, Server, Network, Database, Activity, Shield } from 'lucide-react';
import { api } from '../../lib/api';

export default function ArchitectureWorkspace() {
  const [designs, setDesigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.designs().then(d => { setDesigns(d.designs || []); setLoading(false); }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-spinner"><Activity size={20} /></div>;

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <div className="text-muted" style={{ fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: 4 }}>Architecture Workspace</div>
        <div style={{ fontSize: 20, fontWeight: 700 }}>Infrastructure Design</div>
        <div className="text-secondary text-sm" style={{ marginTop: 4 }}>Provider-neutral architecture modeling. Provider ≠ Platform.</div>
      </div>

      {/* Provider / Platform separation */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <Cpu size={14} style={{ marginRight: 8 }} />Providers
          </div>
          <div className="flex-col gap-sm">
            {['AWS', 'GCP', 'ON_PREM', 'PRIVATE_CLOUD'].map(p => (
              <div key={p} className="flex-between">
                <span className="text-sm">{p}</span>
                <span className="badge badge-draft">NOT EXECUTED</span>
              </div>
            ))}
          </div>
        </div>
        <div className="card">
          <div className="card-title" style={{ marginBottom: 12 }}>
            <Server size={14} style={{ marginRight: 8 }} />Platforms
          </div>
          <div className="flex-col gap-sm">
            {['NATIVE_VM', 'KUBERNETES', 'OPENSHIFT_OCP', 'BARE_METAL'].map(p => (
              <div key={p} className="flex-between">
                <span className="text-sm">{p}</span>
                <span className="text-xs text-muted">
                  {p === 'OPENSHIFT_OCP' ? 'Platform (not provider)' : ''}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Designs */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Architecture Designs</div>
        </div>
        {designs.length === 0 ? (
          <div className="empty-state">
            <Box size={24} className="empty-state-icon" />
            <div className="empty-state-title">No designs yet</div>
            <div className="empty-state-desc">Create an architecture design to define infrastructure topology, components, and dependencies.</div>
          </div>
        ) : (
          <table className="table-compact">
            <thead><tr><th>ID</th><th>Status</th><th>Provider</th><th>Platform</th><th>Created</th></tr></thead>
            <tbody>
              {designs.map((d: any) => (
                <tr key={d.id || d.designId}>
                  <td className="mono">{d.id || d.designId}</td>
                  <td><span className="badge badge-info">{d.status || 'DRAFT'}</span></td>
                  <td>{d.provider || '-'}</td>
                  <td>{d.platform || '-'}</td>
                  <td className="text-xs text-muted">{d.createdAt || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
