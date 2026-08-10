import React, { useState, useEffect, lazy, Suspense } from 'react';
import {
  LayoutDashboard, Box, FileText, Play, ShieldCheck, FileSearch,
  ArrowUpRight, RotateCcw, ClipboardCheck, CheckCircle2,
  Cpu, Settings, Activity
} from 'lucide-react';
import './styles/design-system.css';

const FlightDeck = lazy(() => import('./features/flight-deck/FlightDeck'));
const ArchitectureWorkspace = lazy(() => import('./features/workspaces/ArchitectureWorkspace'));
const ImplementationWorkspace = lazy(() => import('./features/workspaces/ImplementationWorkspace'));
const ExecutionCenter = lazy(() => import('./features/workspaces/ExecutionCenter'));
const EvidenceViewer = lazy(() => import('./features/workspaces/EvidenceViewer'));
const PromotionCenter = lazy(() => import('./features/workspaces/PromotionCenter'));
const RecoveryCenter = lazy(() => import('./features/workspaces/RecoveryCenter'));
const UatWorkspace = lazy(() => import('./features/workspaces/UatWorkspace'));
const ProductionReadiness = lazy(() => import('./features/workspaces/ProductionReadiness'));
const ProviderIntelligence = lazy(() => import('./features/workspaces/ProviderIntelligence'));
const SystemSafety = lazy(() => import('./features/workspaces/SystemSafety'));

type View = 'flight-deck' | 'architecture' | 'implementation' | 'execution'
  | 'evidence' | 'promotion' | 'recovery' | 'uat' | 'production-readiness'
  | 'provider-intel' | 'system';

interface NavItem {
  id: View;
  label: string;
  icon: React.ElementType;
}

const NAV_ITEMS: NavItem[] = [
  { id: 'flight-deck', label: 'Flight Deck', icon: LayoutDashboard },
  { id: 'architecture', label: 'Architecture', icon: Box },
  { id: 'implementation', label: 'Implementation', icon: FileText },
  { id: 'execution', label: 'Execution', icon: Play },
  { id: 'evidence', label: 'Evidence', icon: FileSearch },
  { id: 'promotion', label: 'Promotion', icon: ArrowUpRight },
  { id: 'recovery', label: 'Recovery', icon: RotateCcw },
  { id: 'uat', label: 'UAT', icon: ClipboardCheck },
  { id: 'production-readiness', label: 'Prod Readiness', icon: CheckCircle2 },
  { id: 'provider-intel', label: 'Providers', icon: Cpu },
  { id: 'system', label: 'System', icon: Settings },
];

function LoadingSpinner() {
  return <div className="loading-spinner"><Activity size={20} className="text-muted" /></div>;
}

export default function App() {
  const [view, setView] = useState<View>('flight-deck');
  const [breadcrumb, setBreadcrumb] = useState('Flight Deck');

  useEffect(() => {
    const item = NAV_ITEMS.find(n => n.id === view);
    setBreadcrumb(item?.label ?? 'Flight Deck');
  }, [view]);

  const renderWorkspace = () => {
    return (
      <Suspense fallback={<LoadingSpinner />}>
        {view === 'flight-deck' && <FlightDeck onNavigate={setView} />}
        {view === 'architecture' && <ArchitectureWorkspace />}
        {view === 'implementation' && <ImplementationWorkspace />}
        {view === 'execution' && <ExecutionCenter />}
        {view === 'evidence' && <EvidenceViewer />}
        {view === 'promotion' && <PromotionCenter />}
        {view === 'recovery' && <RecoveryCenter />}
        {view === 'uat' && <UatWorkspace />}
        {view === 'production-readiness' && <ProductionReadiness />}
        {view === 'provider-intel' && <ProviderIntelligence />}
        {view === 'system' && <SystemSafety />}
      </Suspense>
    );
  };

  return (
    <div className="app-shell">
      <nav className="nav-rail">
        <div className="nav-rail-logo">
          <Activity size={18} />
        </div>
        {NAV_ITEMS.map(item => {
          const Icon = item.icon;
          const active = view === item.id;
          return (
            <button
              key={item.id}
              className={`nav-rail-item${active ? ' active' : ''}`}
              onClick={() => setView(item.id)}
              title={item.label}
            >
              <Icon size={18} />
            </button>
          );
        })}
      </nav>

      <div className="app-main">
        <header className="topbar">
          <span className="topbar-title">INFRA-AGAIN</span>
          <span className="text-muted" style={{ fontSize: 10 }}>|</span>
          <span className="topbar-breadcrumb">{breadcrumb}</span>
          <div className="topbar-spacer" />
          <div className="flex-row gap-sm">
            <span className="badge badge-info" style={{ fontSize: 10 }}>SANDBOX: ASK</span>
            <span className="badge badge-blocked" style={{ fontSize: 10 }}>CR: BLOCK</span>
            <span className="badge badge-blocked" style={{ fontSize: 10 }}>PROD: BLOCK</span>
          </div>
        </header>
        <main className="workspace">
          {renderWorkspace()}
        </main>
      </div>
    </div>
  );
}
