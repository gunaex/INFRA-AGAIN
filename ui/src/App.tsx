import { useState, Suspense, lazy } from 'react';

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

const TABS: { id: View; label: string }[] = [
  { id: 'flight-deck', label: 'Flight Deck' },
  { id: 'architecture', label: 'Architecture' },
  { id: 'implementation', label: 'Implementation' },
  { id: 'execution', label: 'Execution' },
  { id: 'evidence', label: 'Evidence' },
  { id: 'promotion', label: 'Promotion' },
  { id: 'recovery', label: 'Recovery' },
  { id: 'uat', label: 'UAT' },
  { id: 'production-readiness', label: 'Prod Readiness' },
  { id: 'provider-intel', label: 'Providers' },
  { id: 'system', label: 'System' },
];

export default function App() {
  const [view, setView] = useState<View>('flight-deck');

  const renderWorkspace = () => (
    <Suspense fallback={<p className="text-gray-500 text-sm p-6">Loading\u2026</p>}>
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

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex flex-wrap items-center justify-between gap-x-4 gap-y-3">
          <div className="flex items-center gap-3 min-w-0">
            <h1 className="text-lg font-semibold text-gray-900 truncate">INFRA-AGAIN</h1>
            <div className="hidden sm:flex items-center gap-1.5">
              <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-cyan-100 text-cyan-700">SANDBOX: ASK</span>
              <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-red-100 text-red-700">CR: BLOCK</span>
              <span className="px-1.5 py-0.5 text-[10px] uppercase tracking-wide rounded bg-red-100 text-red-700">PROD: BLOCK</span>
            </div>
          </div>
          <nav className="flex gap-1.5 flex-wrap">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setView(t.id)}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
                  view === t.id
                    ? 'bg-cyan-600 text-white'
                    : 'text-gray-600 hover:bg-gray-100'
                }`}
              >
                {t.label}
              </button>
            ))}
          </nav>
        </div>
      </header>
      <main className="max-w-6xl mx-auto px-4 sm:px-6 py-6">
        {renderWorkspace()}
      </main>
    </div>
  );
}
