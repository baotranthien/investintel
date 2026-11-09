# InvestIntel — Product Context

## Purpose & Vision
InvestIntel is an institutional-grade, local-first financial research and quantitative decision-support workstation tailored for the Vietnamese equity market (VN100, VN30). It bridges rigorous quantitative multi-factor screening (Valuation, Financial Quality, Price Momentum) with an evidence-grounded AI Analyst that operates strictly on audited financial statements, historical quotes, and verified point-in-time facts — eliminating AI hallucination.

## Primary User & Jobs-to-be-Done
- **Primary User:** Professional equity analyst, active quantitative investor, and portfolio manager navigating HOSE/HNX equities.
- **Operating Context:** Fast-paced market sessions and deep after-hours financial statement due diligence. Users require high scanability, high information density without clutter, tabular numerical precision, and instant sub-second response times.
- **Core Jobs:**
  1. **Market Pulse Monitoring:** Track VN-Index / VN30 regime, advancing/declining market breadth, turnover liquidity, and material disclosures.
  2. **Multi-Factor Screening:** Pinpoint undervalued, high-ROE, positive-momentum equities across VN100 with 3D multi-factor spatial positioning.
  3. **Evidence-Grounded AI Analysis:** Query corporate balance sheets, DCF sensitivity, and DuPont ratios with mandatory footnote-style citation audit trails.
  4. **Portfolio Allocation & Risk Tracking:** Rebalance target weights (Growth, Dividend/Defense, Cash reserves) and track sector concentration.

## Platform & Technical Architecture
- **Platform:** Web application (Desktop-first workstation responsive down to mobile viewports 375px+).
- **Frontend Stack:** Next.js 16 (App Router), React 19, TypeScript, CSS Modules, Three.js / React Three Fiber (Spatial 3D & 2.5D visualizers), Framer Motion.
- **Backend Stack:** FastAPI, Python 3.10+, SQLite database with immutable Point-in-Time financial statement facts and automated lineaged ingestors.
- **Desktop Launcher:** C# .NET Unified Process Supervisor (`InvestIntel.exe`) managing backend and frontend lifecycles with health-check watchdog.

## Core Capabilities & Hard Invariants
1. **Zero Hallucination Grounding:** Every statement made by the AI Analyst must map to an immutable evidence citation pill.
2. **Deterministic Quant Pipeline:** Factor models (P/E, ROE, RS, Margin of Safety) compute deterministically without stochastic drift.
3. **Local-First Speed:** Backend calls proxy locally to `127.0.0.1:8000` with instant client-side memory caching and zero cloud dependency.
4. **WCAG AA Accessibility:** Minimum contrast 4.5:1 for functional text, 44×44px interactive tap targets, no functional text below 11px, visible keyboard focus indicators.

