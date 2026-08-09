import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState,
  type Node, type Edge, MarkerType,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import PulseNode from './components/PulseNode';
import PulseEdge from './components/PulseEdge';
import FlowTimeline from './components/FlowTimeline';
import FlowScenarioSelector from './components/FlowScenarioSelector';
import FlowDetailsPanel from './components/FlowDetailsPanel';
import BottleneckPanel from './components/BottleneckPanel';
import DesignReviewPanel from './components/DesignReviewPanel';
import type {
  FlowDefinition, FlowPlaybackState, FlowEvent, SimulationResult,
  Design, DesignStatus, ScenarioId, FlowNodeState, FlowBottleneck,
} from './model/flowTypes';

const API = (typeof import.meta !== 'undefined' && (import.meta as any)?.env?.VITE_API_URL) || '';

const nodeTypes = { pulseNode: PulseNode };
const edgeTypes = { pulseEdge: PulseEdge };

// Layout: left-to-right
function layoutNodes(flow: FlowDefinition): Node[] {
  return flow.nodes.map((n, i) => ({
    id: n.nodeId,
    type: 'pulseNode',
    position: { x: i * 180 + 20, y: 120 + (i % 2) * 100 },
    data: {
      label: n.label,
      state: 'IDLE' as FlowNodeState,
      category: n.category,
      provider: n.provider,
      description: n.description,
    },
  }));
}

function layoutEdges(flow: FlowDefinition): Edge[] {
  return flow.edges.map((e) => ({
    id: e.edgeId,
    source: e.sourceId,
    target: e.targetId,
    type: 'pulseEdge',
    animated: false,
    markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12 },
    data: { state: 'IDLE', flowType: e.flowType, label: e.label },
  }));
}

export default function InfraPulsePage() {
  const [design, setDesign] = useState<Design | null>(null);
  const [flow, setFlow] = useState<FlowDefinition | null>(null);
  const [simResult, setSimResult] = useState<SimulationResult | null>(null);
  const [events, setEvents] = useState<FlowEvent[]>([]);
  const [playbackMs, setPlaybackMs] = useState(-1);
  const [scenario, setScenario] = useState<ScenarioId>('HAPPY_PATH');
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [view, setView] = useState<'flow' | 'review'>('flow');
  const [loading, setLoading] = useState(false);

  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);

  // Create design
  const createDesign = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(API + '/api/v1/designs?name=Customer+API+Service', { method: 'POST' });
      const d = await r.json();
      const designId = d.design.designId;

      const g = await fetch(API + `/api/v1/designs/${designId}/generate`, { method: 'POST' });
      const gd = await g.json();
      setDesign(gd.design);
      setFlow(gd.flow);
      setNodes(layoutNodes(gd.flow));
      setEdges(layoutEdges(gd.flow));
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [API]);

  // Run simulation
  const runSim = useCallback(async (sc: ScenarioId) => {
    if (!design || !flow) return;
    setScenario(sc);
    setLoading(true);
    try {
      const r = await fetch(
        API + `/api/v1/designs/${design.designId}/simulate?scenario=${sc}&flowId=${flow.flowId}&seed=42`,
        { method: 'POST' }
      );
      const sr: SimulationResult = await r.json();
      setSimResult(sr);
      setEvents(sr.events);
      setPlaybackMs(-1);
      applyState(sr.finalState);
      setPlaying(false);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [design, flow, API]);

  // Apply playback state to nodes/edges
  const applyState = useCallback((state: FlowPlaybackState) => {
    setNodes((nds) => nds.map((n) => ({
      ...n,
      data: {
        ...n.data,
        state: state.nodeStates[n.id] || 'IDLE',
        latencyMs: state.bottlenecks?.find((b: FlowBottleneck) => b.nodeId === n.id)
          ? state.bottlenecks.find((b: FlowBottleneck) => b.nodeId === n.id)?.factors?.[0]?.value
          : undefined,
      },
    })));
    setEdges((eds) => eds.map((e) => ({
      ...e,
      data: { ...e.data, state: state.edgeStates[e.id] || 'IDLE' },
    })));
  }, []);

  // Playback stepping
  useEffect(() => {
    if (!playing || events.length === 0) return;
    const interval = setInterval(() => {
      setPlaybackMs((prev) => {
        const step = 50 / speed;
        const next = prev < 0 ? step : prev + step;
        const maxMs = events[events.length - 1]?.timestampMs || 0;
        if (next >= maxMs) {
          setPlaying(false);
          applyState(simResult?.finalState!);
          return maxMs;
        }
        // Find events at this timestamp
        const activeEvts = events.filter((e) => e.timestampMs <= next);
        if (activeEvts.length > 0) {
          // Reconstruct approximate state
          const nodeStates: Record<string, FlowNodeState> = {};
          const edgeStates: Record<string, any> = {};
          for (const evt of activeEvts) {
            if (evt.eventType === 'NODE_ENTER') nodeStates[evt.nodeId] = 'ACTIVE';
            if (evt.eventType === 'NODE_PASS') nodeStates[evt.nodeId] = 'PASS';
            if (evt.eventType === 'NODE_BLOCK') nodeStates[evt.nodeId] = 'BLOCKED';
            if (evt.eventType === 'NODE_FAIL') nodeStates[evt.nodeId] = 'FAILED';
            if (evt.eventType === 'APPROVAL_REQUESTED') nodeStates[evt.nodeId] = 'WAITING';
            if (evt.eventType === 'BOTTLENECK_DETECTED') nodeStates[evt.nodeId] = 'DEGRADED';
            if (evt.eventType === 'RETRY_START') nodeStates[evt.nodeId] = 'RETRYING';
          }
          applyState({
            flowId: flow?.flowId || '', timestampMs: next,
            nodeStates, edgeStates, activePath: [], bottlenecks: [],
            currentEvent: activeEvts[activeEvts.length - 1],
          });
        }
        return next;
      });
    }, 50 / speed);
    return () => clearInterval(interval);
  }, [playing, events, speed]);

  // Accept design
  const acceptDesign = useCallback(async () => {
    if (!design) return;
    const r = await fetch(API + `/api/v1/designs/${design.designId}/accept?accepted_by=user`, { method: 'POST' });
    const d = await r.json();
    setDesign(d.design);
  }, [design, API]);

  // Request change
  const requestChange = useCallback(async (comment: string) => {
    if (!design) return;
    const r = await fetch(
      API + `/api/v1/designs/${design.designId}/request-change?comment=${encodeURIComponent(comment)}`,
      { method: 'POST' }
    );
    const d = await r.json();
    setDesign(d.design);
  }, [design, API]);

  const scenarioList: ScenarioId[] = ['HAPPY_PATH','AUTH_FAILURE','FIREWALL_BLOCK','DATABASE_SLOW','API_TIMEOUT','APPROVAL_WAIT','RETRY_RECOVERY'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 60px)' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '8px 16px',
        borderBottom: '1px solid #e5e7eb', background: '#f9fafb' }}>
        <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700 }}>Infra Pulse</h2>
        {!design ? (
          <button onClick={createDesign} disabled={loading}
            style={{ padding: '6px 16px', background: '#3b82f6', color: '#fff', border: 'none',
              borderRadius: 6, cursor: 'pointer', fontWeight: 600 }}>
            {loading ? 'Loading...' : 'Create Design'}
          </button>
        ) : (
          <>
            <span style={{ fontSize: 12, color: '#6b7280' }}>{design.designId}</span>
            <span style={{
              padding: '2px 8px', borderRadius: 4, fontSize: 11, fontWeight: 600,
              background: design.status === 'BASELINE_FROZEN' ? '#dcfce7' :
                design.status === 'CHANGE_REQUESTED' ? '#fef3c7' : '#dbeafe',
              color: design.status === 'BASELINE_FROZEN' ? '#166534' :
                design.status === 'CHANGE_REQUESTED' ? '#92400e' : '#1e40af',
            }}>
              {design.status.replace(/_/g, ' ')}
            </span>
          </>
        )}
        <div style={{ flex: 1 }} />
        <div style={{ display: 'flex', gap: 4 }}>
          <button onClick={() => setView('flow')}
            style={{ padding: '4px 12px', background: view === 'flow' ? '#3b82f6' : '#e5e7eb',
              color: view === 'flow' ? '#fff' : '#374151', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Flow
          </button>
          <button onClick={() => setView('review')}
            style={{ padding: '4px 12px', background: view === 'review' ? '#3b82f6' : '#e5e7eb',
              color: view === 'review' ? '#fff' : '#374151', border: 'none', borderRadius: 4, cursor: 'pointer' }}>
            Design Review
          </button>
        </div>
      </div>

      {!design ? (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7280' }}>
          Click "Create Design" to generate an architecture and begin simulation.
        </div>
      ) : view === 'review' ? (
        <DesignReviewPanel design={design} onAccept={acceptDesign} onChangeRequest={requestChange} />
      ) : (
        <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
          {/* Canvas */}
          <div style={{ flex: 1, position: 'relative' }}>
            <ReactFlow
              nodes={nodes} edges={edges}
              onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
              nodeTypes={nodeTypes} edgeTypes={edgeTypes}
              fitView
              onNodeClick={(_, node) => setSelectedNode(node.id)}
              nodesDraggable={false}
            >
              <Background color="#f3f4f6" gap={20} />
              <Controls />
              <MiniMap nodeStrokeWidth={2} pannable zoomable />
            </ReactFlow>
            {/* Legend */}
            <div style={{
              position: 'absolute', bottom: 8, left: 8, background: 'rgba(255,255,255,0.9)',
              borderRadius: 6, padding: '6px 10px', fontSize: 10, border: '1px solid #e5e7eb',
            }}>
              <div style={{ fontWeight: 600, marginBottom: 2 }}>Legend</div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {['REQUEST','DATA','AUTH','APPROVAL','RESPONSE','RETRY'].map((t) => (
                  <span key={t} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                    <span style={{ width: 8, height: 8, borderRadius: 2,
                      background: {REQUEST:'#3b82f6',DATA:'#06b6d4',AUTH:'#8b5cf6',APPROVAL:'#a855f7',RESPONSE:'#10b981',RETRY:'#eab308'}[t] }} />
                    {t}
                  </span>
                ))}
              </div>
              <div style={{ marginTop: 2, fontSize: 9, color: '#9ca3af' }}>
                All metrics: SIMULATED — not live telemetry
              </div>
            </div>
          </div>

          {/* Right sidebar */}
          <div style={{ width: 280, borderLeft: '1px solid #e5e7eb', overflow: 'auto', padding: 12, background: '#fafafa' }}>
            <FlowScenarioSelector scenarios={scenarioList} current={scenario}
              onSelect={(s) => runSim(s as ScenarioId)} disabled={loading} />

            <div style={{ display: 'flex', gap: 4, marginTop: 8, marginBottom: 8 }}>
              <button onClick={() => { setPlaying(!playing); if (playbackMs < 0) setPlaybackMs(0); }}
                style={{ padding: '4px 10px', background: playing ? '#f97316' : '#22c55e', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontWeight: 600, fontSize: 11 }}>
                {playing ? '⏸ Pause' : '▶ Play'}
              </button>
              <button onClick={() => { setPlaying(false); setPlaybackMs(-1); events.length > 0 && applyState(simResult?.finalState!); }}
                style={{ padding: '4px 10px', background: '#6b7280', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: 11 }}>
                ↺ Reset
              </button>
              <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}
                style={{ padding: '2px 4px', border: '1px solid #d1d5db', borderRadius: 4, fontSize: 11 }}>
                <option value={0.5}>0.5x</option><option value={1}>1x</option>
                <option value={2}>2x</option><option value={4}>4x</option>
              </select>
            </div>

            {simResult && (
              <div style={{ fontSize: 10, color: '#6b7280', marginBottom: 8 }}>
                Source: {simResult.source} | Duration: {simResult.durationMs}ms | Events: {events.length}
              </div>
            )}

            {simResult?.bottlenecks && simResult.bottlenecks.length > 0 && (
              <BottleneckPanel bottlenecks={simResult.bottlenecks} />
            )}

            {events.length > 0 && (
              <FlowTimeline events={events} playbackMs={playbackMs}
                onSeek={(ms) => { setPlaybackMs(ms); setPlaying(false); }} />
            )}

            {selectedNode && flow && (
              <FlowDetailsPanel nodeId={selectedNode} flow={flow}
                state={nodes.find((n) => n.id === selectedNode)?.data?.state}
                bottleneck={simResult?.bottlenecks?.find((b) => b.nodeId === selectedNode)} />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
