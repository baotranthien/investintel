export type DataProvider = {
  provider: string;
  status: string;
  last_success: string | null;
  records_last_run: number;
  data_freshness: string;
  requires?: string;
  api_key_configured?: boolean;
  reason?: string | null;
};

export type AssetSummary = {
  symbol: string;
  name: string;
  asset_type: string;
  exchange: string | null;
  sector: string | null;
  status: string;
};

export type MetricStatus = "AVAILABLE" | "STALE" | "INSUFFICIENT_DATA" | "NOT_CONFIGURED";

export type MarketMetric = {
  value: number | null;
  unit: string | null;
  as_of_date: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  source: string | null;
  status: MetricStatus;
  data_origin: string | null;
  note: string | null;
  details: Record<string, unknown>;
};

export type MarketEvent = {
  id: string;
  title: string;
  event_type: string;
  materiality: string;
  severity: number;
  published_at: string | null;
  source: string | null;
  source_documents: string[];
};

export type MarketRegimeSummary = {
  regime: string;
  confidence: number;
  drivers: string[];
  risks: string[];
  changes: string[];
  as_of: string | null;
  model_version: string;
  supporting_signals: string[];
  conflicting_signals: string[];
  data_coverage: number | null;
  historical_context: string[];
  momentum_20d: number | null;
  advancing: number | null;
  declining: number | null;
  unchanged: number | null;
  breadth_percent: number | null;
};

export type MarketDashboard = {
  status: "AVAILABLE" | "PARTIAL" | "INSUFFICIENT_DATA";
  as_of_date: string;
  indexes: Array<{ symbol: string; name: string; metric: MarketMetric }>;
  market_regime: MarketRegimeSummary;
  breadth: MarketMetric;
  momentum: MarketMetric;
  liquidity: MarketMetric;
  foreign_flow: MarketMetric;
  events_status: MetricStatus;
  major_events: MarketEvent[];
};

export type MacroSeriesLatest = {
  series_id: string;
  name: string;
  region: "VIETNAM" | "US" | "CHINA" | "GLOBAL";
  provider: string;
  value: number | null;
  unit: string;
  frequency: string;
  observation_date: string | null;
  release_date: string | null;
  published_at: string | null;
  retrieved_at: string | null;
  source: string | null;
  source_url: string | null;
  source_type: string | null;
  status: "AVAILABLE" | "STALE" | "INSUFFICIENT_DATA";
  data_origin: string | null;
};

export type MacroLatest = {
  as_of_date: string;
  status: "AVAILABLE" | "PARTIAL" | "INSUFFICIENT_DATA";
  regions: Record<MacroSeriesLatest["region"], MacroSeriesLatest[]>;
};

export type OpportunityFilters = {
  universe: "ALL" | "VN100" | "VN300";
  sector: string;
  horizon: "MEDIUM_TERM" | "LONG_TERM";
  scoreMin: string;
  riskMax: string;
  confidence: string;
  factor: string;
  valuationStatus: string;
};

export type OpportunityItem = {
  symbol: string;
  name: string;
  asset_type: string;
  sector: string | null;
  opportunity_score: number | null;
  confidence: string;
  risk_score: number | null;
  valuation_status: string;
  factor_summary: Record<string, number> | null;
  factor_status: string;
  why_now: Array<{ category: string; description: string; direction: string }>;
  why_not_now: Array<{ category: string; description: string; direction: string }>;
  data_status: string;
  data_freshness: { status: string; as_of_date: string | null; source: string | null };
  horizon: string;
  model_version: string;
  what_could_go_wrong?: string[];
};

export type OpportunityScanner = {
  status: "AVAILABLE" | "PARTIAL" | "INSUFFICIENT_DATA" | "UNSUPPORTED_HORIZON";
  as_of_date: string;
  universe: string;
  horizon: string;
  total_assets: number;
  result_count: number;
  sector_options: string[];
  applied_filters: Record<string, unknown>;
  unavailable_filters: string[];
  results: OpportunityItem[];
  note: string | null;
};

export type ResearchEvidence = {
  claim_type: "FACT" | "MODEL_OUTPUT" | "INTERPRETATION" | "HYPOTHESIS" | "UNCERTAINTY";
  source: string | null;
  source_url: string | null;
  observation_date: string | null;
  publication_date: string | null;
  retrieved_at: string | null;
  data_origin: string | null;
  note: string | null;
};

export type ResearchMetric = {
  value: number | null;
  unit: string | null;
  status: "AVAILABLE" | "STALE" | "INSUFFICIENT_DATA" | "NOT_MEANINGFUL";
  period: string | null;
  calculation: string | null;
  evidence: ResearchEvidence;
};

export type ResearchTimelineItem = {
  id: string;
  date: string | null;
  kind: string;
  title: string;
  before: string | null;
  current: string | null;
  status: string;
  evidence: ResearchEvidence;
};

export type ResearchWorkspace = {
  as_of_date: string;
  status: "AVAILABLE" | "PARTIAL" | "INSUFFICIENT_DATA";
  asset: {
    symbol: string;
    name: string;
    asset_type: string;
    exchange: string | null;
    sector: string;
    currency: string;
    status: string;
  };
  price: {
    value: number | null;
    as_of_date: string | null;
    source: string | null;
    status: string;
    data_origin: string;
    retrieved_at: string | null;
    source_url: string | null;
  };
  opportunity: {
    score: number | null;
    confidence: string;
    risk: number | null;
    horizon: string;
    status: string;
    why_now: Array<Record<string, unknown>>;
    why_not_now: Array<Record<string, unknown>>;
    what_would_make_me_wrong: Array<Record<string, unknown>>;
  };
  fundamentals: {
    status: string;
    metrics: Record<string, ResearchMetric>;
    period: string | null;
    history: Array<{
      period_end: string | null;
      publication_date: string | null;
      fiscal_year: number | null;
      fiscal_quarter: number | null;
      period_type: string | null;
      revenue: number | null;
      earnings: number | null;
      eps: number | null;
      source: string | null;
    }>;
    ttm_available: boolean;
    earnings_quality: Record<string, unknown> | null;
    financial_health: unknown;
    quality_flags: Array<Record<string, unknown>>;
    sources: string[];
    latest_publication_date: string | null;
  };
  sector_analysis: {
    sector: string;
    status: string;
    applicable_metrics: string[];
    not_applicable_metrics: string[];
    metrics: Record<string, ResearchMetric>;
    notes: string[];
  };
  valuation: {
    status: string;
    metrics: Record<string, ResearchMetric>;
    fair_value: null | { bear: number; base: number; bull: number };
    scenarios: Array<Record<string, unknown>>;
    warnings: string[];
  };
  factors: { status: string; scores: Record<string, ResearchMetric>; supporting: string[]; contradicting: string[] };
  risk: {
    status: string;
    overall_score: number | null;
    top_contributors: string[];
    missing_data_warning: string;
    categories: Array<{ name: string; value: number | null; status: string; drivers: string[] }>;
  };
  macro_sensitivity: { status: string; sensitivities: Array<Record<string, unknown>>; note: string };
  events: Array<Record<string, unknown>>;
  timeline: ResearchTimelineItem[];
  research_summary: {
    what_changed: Array<Record<string, unknown>>;
    why_now: Array<Record<string, unknown>>;
    why_not_now: Array<Record<string, unknown>>;
    what_would_make_me_wrong: Array<Record<string, unknown>>;
  };
  data_quality: {
    status: string;
    price_status: string;
    financial_status: string;
    source_origin: string;
    history_depth_years: number;
    stale_warning: boolean;
    as_of_date: string;
  };
};

export type PortfolioHolding = {
  id: number;
  symbol: string;
  name: string;
  sector: string | null;
  asset_type: string;
  quantity: number;
  average_cost: number;
  acquisition_date: string;
  role: "CORE" | "SATELLITE" | "UNASSIGNED";
  horizon: "MEDIUM_TERM" | "LONG_TERM" | null;
  notes: string | null;
  current_price: number | null;
  price_as_of: string | null;
  price_source: string | null;
  price_status: string;
  cost_basis: number;
  market_value: number | null;
  unrealized_pnl: number | null;
  target_weight: number | null;
  current_weight: number | null;
};

export type PortfolioDashboard = {
  portfolio_id: string;
  as_of_date: string;
  status: "EMPTY" | "AVAILABLE" | "PARTIAL";
  summary: { holdings_count: number; total_value: number | null; cost_basis: number; unrealized_pnl: number | null; currency: string; value_status: string };
  holdings: PortfolioHolding[];
  allocation: { status: string; sector: Array<{ sector: string; market_value: number; weight: number }>; core_satellite: Array<{ role: string; market_value: number; weight: number }> };
  concentration: { single_name_limit: number | null; sector_limit: number | null; warnings: Array<Record<string, unknown>> };
  risk_exposure: { status: string; value: number | null; note: string };
  factor_exposure: { status: string; value: number | null; note: string };
};

export type PortfolioSettings = {
  portfolio_id: string;
  name: string;
  base_currency: string;
  single_name_limit: number | null;
  sector_limit: number | null;
  core_target: number | null;
  satellite_target: number | null;
  material_change_threshold: number | null;
};

export type PortfolioTargets = { status: string; targets: Array<{ symbol: string; target_weight: number }>; total_weight: number };

export type DcaPlan = {
  saved: boolean;
  status: string;
  monthly_amount: number;
  range: { minimum: number; maximum: number; currency: string };
  core_pct: number;
  satellite_pct: number;
  reserve_pct: number;
  current_allocation: PortfolioDashboard["allocation"];
  routes: Array<{ symbol: string; amount: number; target_weight: number; weight_gap: number; status: string }>;
  unused_or_satellite_reserve: number;
  note: string;
};

export type PortfolioFit = {
  portfolio_id: string;
  as_of_date: string;
  status: string;
  items: Array<{
    symbol: string;
    portfolio_role: string;
    current_weight: number | null;
    target_weight: number | null;
    sector: string | null;
    sector_weight: number | null;
    sector_overlap: string;
    opportunity_score: number | null;
    confidence: string;
    risk_score: number | null;
    risk_overlap: string;
    factor_overlap: string;
    horizon_compatibility: string;
    status: string;
    note: string;
  }>;
};

export type WatchlistItem = {
  id: number;
  symbol: string;
  name: string;
  sector: string | null;
  thesis: string | null;
  horizon: string | null;
  invalidation: string | null;
  last_reviewed_at: string | null;
  last_changed_at: string;
  opportunity: number | null;
  confidence: string;
  risk: number | null;
  valuation: Record<string, { value: number | null; status: string }> | null;
  why_now: Array<Record<string, unknown>>;
  why_not_now: Array<Record<string, unknown>>;
  data_status: string;
  data_freshness: { status: string; as_of_date: string | null; source: string | null };
  changes: Array<Record<string, unknown>>;
};

export type DecisionScenario = {
  status: "AVAILABLE" | "INSUFFICIENT_DATA";
  assumptions: string[];
  key_drivers: string[];
  valuation_range: string | null;
  risks: string[];
  confidence: "HIGH" | "MEDIUM" | "LOW" | "INSUFFICIENT_DATA";
  uncertainty: string | null;
};

export type DecisionChange = {
  claim_type: string;
  responsible_module: string;
  metric: string | null;
  before: unknown;
  after: unknown;
  date: string;
  magnitude: { absolute: number; relative_pct: number | null } | null;
  source: string | null;
  evidence: Array<Record<string, unknown>>;
};

export type DecisionContext = {
  symbol: string;
  decision_state: string;
  what_changed: DecisionChange[];
  why_now: Array<Record<string, unknown>>;
  why_not_now: Array<Record<string, unknown>>;
  what_would_make_me_wrong: Array<Record<string, unknown>>;
  scenario: Record<"bear" | "base" | "bull", DecisionScenario>;
  evidence: Array<Record<string, unknown>>;
  timeline: Array<Record<string, unknown>>;
  explainability: Record<string, { status: string; value: unknown; evidence: Array<Record<string, unknown>>; note: string | null }>;
  as_of_date: string;
  snapshot: Record<string, unknown>;
};

export type DecisionSnapshotReceipt = {
  id: number;
  symbol: string;
  as_of_date: string;
  captured_at: string;
};

export type AIToolName =
  | "asset" | "fundamentals" | "valuation" | "factors" | "risk" | "macro" | "regime"
  | "events" | "opportunity" | "portfolio" | "watchlist" | "historical_snapshot"
  | "evidence" | "document_retrieval";

export type AIClaim = {
  claim_type: "FACT" | "MODEL_OUTPUT" | "INTERPRETATION" | "HYPOTHESIS" | "UNCERTAINTY";
  text: string;
  citation_ids: string[];
};

export type AICitation = {
  id: string;
  claim_type: AIClaim["claim_type"];
  responsible_module: string;
  source: string | null;
  source_url: string | null;
  observation_date: string | null;
  publication_date: string | null;
  retrieved_at: string | null;
  data_origin: string | null;
  freshness: string | null;
  note: string | null;
};

export type AIStatus = {
  status: "HEALTHY" | "DEGRADED" | "UNAVAILABLE" | "NOT_CONFIGURED";
  available: boolean;
  provider: string;
  version?: string | null;
  models: string[];
  configured_models?: Record<string, string>;
  configured_model_installed?: boolean;
  configured_model_loaded?: boolean;
  running_models?: Array<Record<string, unknown>>;
  gpu?: { available: boolean; name: string | null; memory_total_mib: number | null; memory_used_mib: number | null };
  reason?: string;
};

export type AIChatRequest = {
  question: string;
  symbol?: string;
  as_of_date?: string;
  tool_names: AIToolName[];
};

export type AIChatResponse = {
  status: "AVAILABLE" | "PARTIAL" | "INSUFFICIENT_DATA";
  symbol: string | null;
  as_of_date: string;
  prompt_version: string;
  model: string | null;
  answer: string;
  claims: AIClaim[];
  citations: AICitation[];
  uncertainty: string[];
  tools_used: AIToolName[];
  usage: Record<string, unknown>;
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiGet<T>(path: `/api/${string}`, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "GET",
    headers: {
      Accept: "application/json",
      "Cache-Control": "no-store",
    },
    credentials: "include",
    cache: "no-store",
    signal,
  });

  if (!response.ok) {
    const responseText = await response.text();
    let detail = responseText;
    try {
      const payload: unknown = JSON.parse(responseText);
      if (typeof payload === "object" && payload !== null && "detail" in payload) {
        detail = String(payload.detail);
      }
    } catch {
      detail = responseText || response.statusText;
    }
    throw new ApiError(detail || "Không thể tải dữ liệu từ API.", response.status);
  }

  return (await response.json()) as T;
}

export function getDataProviders(signal?: AbortSignal) {
  return apiGet<DataProvider[]>("/api/v1/data/providers", signal);
}

export function getAssets(signal?: AbortSignal) {
  return apiGet<AssetSummary[]>("/api/v1/assets", signal);
}

export function getMarketDashboard(signal?: AbortSignal) {
  return apiGet<MarketDashboard>("/api/v1/market/dashboard", signal);
}

export function getLatestMacro(signal?: AbortSignal) {
  return apiGet<MacroLatest>("/api/v1/macro/observations/latest", signal);
}

export function getOpportunityScanner(filters: OpportunityFilters, signal?: AbortSignal) {
  const params = new URLSearchParams({ universe: filters.universe, horizon: filters.horizon });
  if (filters.sector) params.set("sector", filters.sector);
  if (filters.scoreMin) params.set("score_min", filters.scoreMin);
  if (filters.riskMax) params.set("risk_max", filters.riskMax);
  if (filters.confidence) params.set("confidence", filters.confidence);
  if (filters.factor) params.set("factor", filters.factor);
  if (filters.valuationStatus) params.set("valuation_status", filters.valuationStatus);
  return apiGet<OpportunityScanner>(`/api/v1/opportunities?${params.toString()}`, signal);
}

export function getResearchWorkspace(symbol: string, asOf?: string, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  const query = params.size ? `?${params.toString()}` : "";
  return apiGet<ResearchWorkspace>(`/api/v1/research/${encodeURIComponent(symbol)}${query}`, signal);
}

export const getPortfolio = (signal?: AbortSignal) => apiGet<PortfolioDashboard>("/api/v1/portfolio", signal);
export const getPortfolioSettings = (signal?: AbortSignal) => apiGet<PortfolioSettings>("/api/v1/portfolio/settings", signal);
export const getPortfolioTargets = (signal?: AbortSignal) => apiGet<PortfolioTargets>("/api/v1/portfolio/targets", signal);
export const getPortfolioDca = (signal?: AbortSignal) => apiGet<DcaPlan>("/api/v1/portfolio/dca", signal);
export const getPortfolioFit = (signal?: AbortSignal) => apiGet<PortfolioFit>("/api/v1/portfolio/fit", signal);
export const getManualTransactions = (signal?: AbortSignal) => apiGet<{ mode: string; transactions: Array<Record<string, unknown>> }>("/api/v1/portfolio/transactions", signal);
export const getPortfolioTemplates = (signal?: AbortSignal) => apiGet<{ templates: Array<{ id: string; label: string; classification: string; targets: Array<{ symbol: string; target_weight: number }>; note: string }> }>("/api/v1/portfolio/templates", signal);
export const getWatchlist = (signal?: AbortSignal) => apiGet<WatchlistItem[]>("/api/v1/watchlist", signal);
export function getDecisionContext(symbol: string, asOf?: string, signal?: AbortSignal) {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  const query = params.size ? `?${params.toString()}` : "";
  return apiGet<DecisionContext>(`/api/v1/decision/${encodeURIComponent(symbol)}${query}`, signal);
}

export async function apiWrite<T>(path: `/api/${string}`, method: "POST" | "PUT" | "PATCH" | "DELETE", payload?: unknown): Promise<T> {
  const response = await fetch(path, {
    method,
    headers: payload === undefined
      ? { Accept: "application/json", "Cache-Control": "no-store" }
      : { Accept: "application/json", "Content-Type": "application/json", "Cache-Control": "no-store" },
    body: payload === undefined ? undefined : JSON.stringify(payload),
    credentials: "include",
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    let message = text || response.statusText;
    try {
      const parsed: unknown = JSON.parse(text);
      if (typeof parsed === "object" && parsed !== null && "detail" in parsed) message = String(parsed.detail);
    } catch { /* retain the response body */ }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function loginUser(password: string): Promise<{ status: string; expires_in: number }> {
  return apiWrite("/api/v1/auth/login", "POST", { password });
}

export async function logoutUser(): Promise<{ status: string }> {
  return apiWrite("/api/v1/auth/logout", "POST", {});
}

export async function getAuthSession(signal?: AbortSignal): Promise<{ authenticated: boolean; user?: string }> {
  return apiGet("/api/v1/auth/session", signal);
}

export const createPortfolioHolding = (payload: Record<string, unknown>) => apiWrite<PortfolioHolding>("/api/v1/portfolio/holdings", "POST", payload);
export const patchPortfolioHolding = (id: number, payload: Record<string, unknown>) => apiWrite<PortfolioHolding>(`/api/v1/portfolio/holdings/${id}`, "PATCH", payload);
export const deletePortfolioHolding = (id: number) => apiWrite<void>(`/api/v1/portfolio/holdings/${id}`, "DELETE");
export const patchPortfolioSettings = (payload: Record<string, unknown>) => apiWrite<PortfolioSettings>("/api/v1/portfolio/settings", "PATCH", payload);
export const putPortfolioTargets = (targets: Array<{ symbol: string; target_weight: number }>) => apiWrite<PortfolioTargets>("/api/v1/portfolio/targets", "PUT", { targets });
export const putPortfolioDca = (payload: { monthly_amount: number; core_pct: number; satellite_pct: number }) => apiWrite<DcaPlan>("/api/v1/portfolio/dca", "PUT", payload);
export const applyPortfolioTemplate = (templateId: string) => apiWrite<PortfolioTargets>(`/api/v1/portfolio/templates/${encodeURIComponent(templateId)}/apply`, "POST");
export const createManualTransaction = (payload: Record<string, unknown>) => apiWrite<Record<string, unknown>>("/api/v1/portfolio/transactions", "POST", payload);
export const createPortfolioSnapshot = () => apiWrite<Record<string, unknown>>("/api/v1/portfolio/snapshot", "POST");
export const createWatchlistItem = (payload: Record<string, unknown>) => apiWrite<WatchlistItem>("/api/v1/watchlist", "POST", payload);
export const patchWatchlistItem = (id: number, payload: Record<string, unknown>) => apiWrite<WatchlistItem>(`/api/v1/watchlist/${id}`, "PATCH", payload);
export const deleteWatchlistItem = (id: number) => apiWrite<void>(`/api/v1/watchlist/${id}`, "DELETE");
export const reviewWatchlistItem = (id: number) => apiWrite<WatchlistItem>(`/api/v1/watchlist/${id}/review`, "POST");
export const captureWatchlistSnapshot = (id: number) => apiWrite<Record<string, unknown>>(`/api/v1/watchlist/${id}/snapshot`, "POST");
export function captureDecisionSnapshot(symbol: string, asOf?: string) {
  const params = new URLSearchParams();
  if (asOf) params.set("as_of", asOf);
  const query = params.size ? `?${params.toString()}` : "";
  return apiWrite<DecisionSnapshotReceipt>(`/api/v1/decision/${encodeURIComponent(symbol)}/snapshot${query}`, "POST");
}
export const getAIStatus = (signal?: AbortSignal) => apiGet<AIStatus>("/api/v1/ai/status", signal);
export const submitAIQuestion = (payload: AIChatRequest) => apiWrite<AIChatResponse>("/api/v1/ai/chat", "POST", payload);

export type BacktestConfig = {
  universe: string[];
  start_date: string;
  end_date: string;
  horizon?: string;
  benchmark?: string;
  initial_capital?: number;
  transaction_cost_pct?: number;
  tax_pct?: number;
  slippage_pct?: number;
  strategy?: string;
};

export type BacktestPoint = {
  date: string;
  portfolio_value: number;
  benchmark_value: number;
  drawdown: number;
};

export type BacktestTrade = {
  date: string;
  symbol: string;
  action: string;
  shares: number;
  price: number;
  value: number;
  fee: number;
  tax: number;
  slippage: number;
};

export type BacktestResult = {
  status: string;
  strategy: string;
  universe: string[];
  start_date: string;
  end_date: string;
  initial_capital: number;
  final_value: number;
  net_profit: number;
  total_return: number;
  annualized_return: number;
  benchmark_return: number;
  alpha: number;
  max_drawdown: number;
  volatility: number;
  sharpe_ratio: number;
  total_trades: number;
  total_fees: number;
  total_taxes: number;
  total_slippage: number;
  equity_curve: BacktestPoint[];
  trades: BacktestTrade[];
  look_ahead_audit: Record<string, unknown>;
  data_quality: Record<string, unknown>;
};

export type AutomationBrief = {
  id: number;
  brief_type: string;
  as_of_date: string;
  status: string;
  payload: Record<string, unknown>;
  idempotency_key: string;
  created_at: string;
};

export type AutomationAlert = {
  id: number;
  alert_id: string;
  symbol: string | null;
  kind: string;
  status: string;
  payload: Record<string, unknown>;
  created_at: string;
  resolved_at: string | null;
};

export const runBacktest = (payload: BacktestConfig) => apiWrite<BacktestResult>("/api/v1/research/backtest", "POST", payload);

export const getAutomationBriefs = (params?: Record<string, string>, signal?: AbortSignal) => {
  const query = params ? `?${new URLSearchParams(params).toString()}` : "";
  return apiGet<{ total: number; items: AutomationBrief[] }>(`/api/v1/automation/briefs${query}`, signal);
};

export const getAutomationBrief = (id: number, signal?: AbortSignal) =>
  apiGet<AutomationBrief>(`/api/v1/automation/briefs/${id}`, signal);

export const getAutomationAlerts = (params?: Record<string, string>, signal?: AbortSignal) => {
  const query = params ? `?${new URLSearchParams(params).toString()}` : "";
  return apiGet<{ total: number; items: AutomationAlert[] }>(`/api/v1/automation/alerts${query}`, signal);
};

export const getAutomationAlert = (id: string, signal?: AbortSignal) =>
  apiGet<AutomationAlert>(`/api/v1/automation/alerts/${encodeURIComponent(id)}`, signal);