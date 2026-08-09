import React, { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import type { FlowNodeState, NodeCategory } from '../model/flowTypes';
import { STATE_COLORS, STATE_LABELS } from '../model/flowTypes';

interface PulseNodeData {
  label: string;
  state: FlowNodeState;
  category: NodeCategory;
  provider?: string;
  description?: string;
  latencyMs?: number;
}

const CATEGORY_ICONS: Record<string, string> = {
  USER: '👤', IDENTITY: '🔑', SECURITY: '🛡', NETWORK: '🌐',
  GATEWAY: '🚪', APPLICATION: '⚙', SERVICE: '🔧', WORKFLOW: '📋',
  DATABASE: '🗄', STORAGE: '💾', QUEUE: '📬', CACHE: '⚡',
  OBSERVABILITY: '📊', EXTERNAL: '🔗', APPROVAL: '✅',
  PROVIDER: '☁', PLATFORM: '🖥',
};

function PulseNode({ data, selected }: NodeProps) {
  const d = data as unknown as PulseNodeData;
  const color = STATE_COLORS[d.state] || '#6b7280';
  const icon = CATEGORY_ICONS[d.category] || '⬡';
  const isBlocked = d.state === 'BLOCKED' || d.state === 'FAILED';
  const isActive = d.state === 'ACTIVE' || d.state === 'RETRYING';
  const isDegraded = d.state === 'DEGRADED';
  const isWaiting = d.state === 'WAITING';
  const isPass = d.state === 'PASS' || d.state === 'COMPLETED';
  const isIdle = d.state === 'IDLE' || d.state === 'NOT_REACHED';

  return (
    <div
      className="pulse-node"
      style={{
        border: `2px solid ${color}`,
        background: isBlocked ? '#fef2f2' : isActive ? '#eff6ff' :
                    isWaiting ? '#faf5ff' : isDegraded ? '#fff7ed' :
                    isPass ? '#f0fdf4' : isIdle ? '#f9fafb' : '#fff',
        borderRadius: 8,
        padding: '8px 14px',
        minWidth: 120,
        opacity: d.state === 'NOT_REACHED' ? 0.4 : 1,
        boxShadow: selected ? `0 0 0 2px ${color}` : '0 1px 3px rgba(0,0,0,0.12)',
        transition: 'border-color 0.3s, background 0.3s, opacity 0.3s',
      }}
    >
      <Handle type="target" position={Position.Left} style={{ background: color }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12 }}>
        <span>{icon}</span>
        <span style={{ fontWeight: 600, color: '#1f2937' }}>{d.label}</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 10 }}>
        <span style={{
          display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: color,
          animation: isActive ? 'pulse-dot 1s infinite' : 'none',
        }} />
        <span style={{ color }}>{STATE_LABELS[d.state] || d.state}</span>
      </div>
      {d.latencyMs != null && (
        <div style={{ fontSize: 10, color: '#6b7280', marginTop: 2 }}>{d.latencyMs} ms</div>
      )}
      {d.provider && (
        <div style={{ fontSize: 9, color: '#9ca3af' }}>{d.provider}</div>
      )}
      <Handle type="source" position={Position.Right} style={{ background: color }} />
    </div>
  );
}

export default memo(PulseNode);
