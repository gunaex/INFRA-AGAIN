/* Shared API client for INFRA-AGAIN Flight Deck */
const BASE = (import.meta as any).env?.VITE_API_URL ?? '';

async function request<T = any>(path: string, opts?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...opts?.headers },
    ...opts,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export const api = {
  get: <T = any>(path: string) => request<T>(path),
  post: <T = any>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined }),

  // Environments
  environments: () => api.get<{ environments: any[] }>('/api/v1/environments'),

  // Promotions
  promotions: () => api.get<{ promotions: any[] }>('/api/v1/promotions'),
  createPromotion: (body: any) => api.post('/api/v1/promotions', body),
  getPromotion: (id: string) => api.get<{ promotion: any }>(`/api/v1/promotions/${id}`),
  approvePromotion: (id: string, approvedBy: string) =>
    api.post(`/api/v1/promotions/${id}/approve?approved_by=${encodeURIComponent(approvedBy)}`),
  rejectPromotion: (id: string) => api.post(`/api/v1/promotions/${id}/reject`),
  consumePromotion: (id: string) => api.post(`/api/v1/promotions/${id}/consume`),
  verifyPromotion: (id: string) => api.get(`/api/v1/promotions/${id}/verify`),

  // Rollback
  rollbackPlans: () => api.get<{ rollbackPlans: any[] }>('/api/v1/rollback-plans'),
  createRollback: (body: any) => api.post('/api/v1/rollback-plans', body),
  getRollback: (id: string) => api.get<{ rollbackPlan: any }>(`/api/v1/rollback-plans/${id}`),
  approveRollback: (id: string, approvedBy: string) =>
    api.post(`/api/v1/rollback-plans/${id}/approve?approved_by=${encodeURIComponent(approvedBy)}`),

  // UAT
  uats: () => api.get<{ uats: any[] }>('/api/v1/uat'),
  createUat: (body: any) => api.post('/api/v1/uat', body),
  getUat: (id: string) => api.get<{ uat: any }>(`/api/v1/uat/${id}`),
  passUat: (id: string, performedBy: string, approvedBy: string) =>
    api.post(`/api/v1/uat/${id}/pass?performed_by=${encodeURIComponent(performedBy)}&approved_by=${encodeURIComponent(approvedBy)}`),

  // Production Readiness
  readinessList: () => api.get<{ readinessRecords: any[] }>('/api/v1/production-readiness'),
  evaluateReadiness: (body: any) => api.post('/api/v1/production-readiness/evaluate', body),
  getReadiness: (id: string) => api.get(`/api/v1/production-readiness/${id}`),

  // Legacy endpoints (for Architecture, Implementation, Execution views)
  designs: () => api.get<{ designs: any[] }>('/api/v1/designs'),
  implementationPlans: () => api.get<{ plans?: any[]; implementation_plans?: any[] }>('/api/v1/implementation-plans'),
  executionPackages: () => api.get<{ packages?: any[]; execution_packages?: any[] }>('/api/v1/execution-packages'),
  runs: () => api.get<{ runs: any[] }>('/api/v1/runs'),
  targets: () => api.get<{ targets: any[] }>('/api/v1/targets'),
  capabilities: () => api.get<any[]>('/api/v1/capabilities?verified_only=true'),
  runners: () => api.get<{ runners: any[] }>('/api/v1/runners'),

  // Design flow
  createDesign: (body: any) => api.post('/api/v1/designs', body),
  getDesign: (id: string) => api.get(`/api/v1/designs/${id}`),
  acceptDesign: (id: string) => api.post(`/api/v1/designs/${id}/accept`),
};
