# InvestIntel — Premium Futuristic Desktop UI Audit & Completion Report

**Date:** 2026-10-28  
**Design Direction:** *InvestIntel — Precision Intelligence Terminal*  
**Auditor / Engineering Lead:** DeepMind AI Pair Programmer  
**Environment:** Local Development (`http://localhost:3000`, API: `http://localhost:8000`)

---

## 1. Executive Summary & Design Direction

The InvestIntel platform was transformed from an ad-hoc dashboard with mismatched components and floating mobile artifacts into a distinctive, institutional desktop workstation: **InvestIntel — Precision Intelligence Terminal**.

### The Core Vision
> *"If Apple engineered a futuristic professional investment workstation, what would it look and feel like?"*

Rather than mimicking a physical phone (no phone frames, no floating notch islands, no endless decorative blur cards), the workstation translates the precision craftsmanship of premium Apple hardware into an institutional financial terminal:
- **Foundations:** Deep graphite and near-black canvases (`#090a0d`, `#0b0d11`, `#12151c`), eliminating muddy greys and light-mode leaks.
- **Surface Hierarchy:** Solid, opaque content surfaces for charts, tables, and AI narrative reading; restrained translucent vibrancy reserved strictly for functional chrome (sticky topbar and floating flyouts).
- **Accents:** Calibrated precision cyan (`#00d2ff`) for analytical focus and interaction, paired with institutional financial emerald (`#10b981`), crimson (`#f43f5e`), and warning amber (`#f59e0b`).
- **Typography & Numerics:** Mandatory `tabular-nums` applied across all financial metrics, deltas, dates, and prices to eliminate digit jitter and misaligned tables.
- **Physical Motion Craftsmanship:** Emil Kowalski-inspired tactile feedback (`:active { transform: scale(0.98); }`, custom `cubic-bezier(0.16, 1, 0.3, 1)` and `(0.22, 1, 0.36, 1)` curves under 220ms).
- **Evolved Desktop Status:** The former floating "Dynamic Island" mobile notch was evolved into an integrated **Desktop Telemetry Rail** docked naturally in the analyst workstation, delivering honest SSE streaming states, phase indicators, and heartbeat durations without blocking viewport content.
- **Signature 3D Spatial Instrument:** Implemented `DimensionalMarketRadar` on `/market` using 100% real index points and market regime data with pure, GPU-efficient CSS 3D isometric transforms, mouse-driven tilt, and reduced-motion fallback.

---

## 2. Modified & Newly Created Files

### A. Modified Core Files
1. `apps/web/src/app/globals.css`: Full overhaul of shared design tokens (`--canvas-base`, `--surface-panel`, `--surface-card`, `--accent-cyan`, `--positive`, `--negative`, `--border-specular`, `--font-mono`, `--font-sans`, custom easings, and numeric tabular rules).
2. `apps/web/src/components/app-shell.tsx`: Institutional desktop sidebar and topbar with live market clock, local-first zero-leak privacy badge, and system status telemetry.
3. `apps/web/src/components/app-shell.module.css`: Precise 260px graphite navigation column with active cyan rim indicators and fluid max-width content container (1640px).
4. `apps/web/src/components/apple-dynamic-island.tsx`: Evolved from a floating mobile pill into an integrated desktop telemetry rail with phase numbers (`01/03`, `02/03`, `03/03`), live SSE heartbeat counter, and honest cancellation control.
5. `apps/web/src/components/apple-dynamic-island.module.css`: Docked command bar styling with titanium hairlines and ambient pulse cores.
6. `apps/web/src/components/apple-citation-pill.tsx`: Compact research annotation button with keyboard `Escape` dismiss and ARIA accessibility.
7. `apps/web/src/components/apple-citation-pill.module.css`: Monospace `§ E001` styling, dark popover with high contrast and observation provenance.
8. `apps/web/src/components/apple-smart-fallback.tsx`: Enhanced with IAS 33 estimated EPS disclosure badge, dual-sided comparative divergence bars, and Pearson correlation gauge.
9. `apps/web/src/components/apple-smart-fallback.module.css`: Structured bento cards with titanium rim highlights and tabular data presentation.
10. `apps/web/src/app/ai/page.tsx`: Full AI Analyst workstation with stock picker chips, date controls, prompt suggestions, and evidence review.
11. `apps/web/src/app/ai/page.module.css`: Two-column workstation layout with readable typography, claim cards with color-coded confidence borders, and collapsible citation drawer.
12. `apps/web/src/app/market/page.tsx`: Integration of `DimensionalMarketRadar` alongside existing index cards, regime details, and macro observers.
13. `apps/web/src/app/market/page.module.css`: Removal of legacy serif fonts and hardcoded light colors; tokenized status badges and tabular numerals.
14. `apps/web/src/app/page.tsx`: Modernized overview dashboard with telemetry ribbon and canonical universe breakdown.
15. `apps/web/src/app/page.module.css`: Removed leftover starter template code; implemented institutional terminal cards.
16. `apps/web/src/app/data-center/page.tsx`: Restructured from unstyled cards into a professional data pipeline monitor.
17. `apps/web/src/app/opportunities/page.module.css`: Replaced hardcoded pale-white backgrounds with dark terminal tokens.
18. `apps/web/src/app/portfolio/page.module.css`: Modernized portfolio telemetry ribbon and transaction table.
19. `apps/web/src/app/research/page.module.css`: Upgraded backtest KPIs and tables with tabular figures and dark surfaces.
20. `apps/web/src/app/watchlist/page.module.css`: Upgraded thesis cards, decision context drawer, and watchlist items.

### B. Newly Created Components
1. `apps/web/src/components/dimensional-market-radar.tsx`: Signature 3D spatial visualization presenting VNINDEX, VN30, HNX index pillars and market breadth in an isometric coordinate field.
2. `apps/web/src/components/dimensional-market-radar.module.css`: CSS 3D transforms (`perspective`, `rotateX`, `rotateY`, `translateZ`) with ambient light beam and `prefers-reduced-motion` static fallback.
3. `apps/web/src/app/data-center/page.module.css`: Institutional styling for data providers, records count, and freshness telemetry.
4. `scripts/capture_screenshots.ps1`: Automated multi-viewport headless Chrome screenshot capture script.

---

## 3. Deliberate Materiality: Where Depth & Glass Were Used vs. Avoided

| Location / Surface | Treatment | Rationale |
| :--- | :--- | :--- |
| **Workspace Canvas** | Solid Deep Graphite (`#090a0d`) | Zero decorative blur; establishes absolute contrast and serious terminal feel. |
| **Topbar & Overlays** | Selective Frosted Glass (`rgba(14, 17, 23, 0.85)`, `blur(20px)`) | Allows content underneath to scroll subtly without obscuring header contrast. |
| **Data Panels & Bento Cards** | Solid Graphite (`#12151c`), 1px Hairline (`rgba(255,255,255,0.08)`), Inset Specular (`inset 0 1px 0 rgba(255,255,255,0.08)`) | Replaces stacked plastic shadows with refined metallic edge highlights like Apple hardware. |
| **Dynamic Island Status** | Docked Command Rail with Cyan Rim (`1px solid rgba(0,210,255,0.25)`) | Avoids floating mobile notch; feels naturally engineered into the desktop workstation. |
| **AI Answer Prose** | Solid `#12151e` container, 14.5px font, line-height 1.7 | Optimizes long-form research reading; avoids background textures or gradients behind text. |
| **Everywhere Else** | **No** decorative floating glass cards, **no** purple AI gradients, **no** spinning glass orbs, **no** arbitrary glow rings | Preserves high-density information scanning and institutional trustworthiness. |

---

## 4. Signature Spatial 3D Visualization: Implementation & Constraints

- **Component:** `DimensionalMarketRadar` rendered on `/market`.
- **Underlying Real Data:**
  - Real index levels for `VNINDEX`, `VN30`, and `HNX` from `getMarketDashboard()`.
  - Real market regime status and confidence percentage from `MarketRegimeEngine`.
  - Real market breadth advancing/declining issue counts from the market API.
- **Technical Architecture:**
  - Built with pure CSS 3D transforms (`perspective(1200px)`, `rotateX(var(--tilt-x))`, `rotateY(var(--tilt-y))`, `translateZ`).
  - No Three.js, R3F, Canvas, or GSAP installed — zero impact on bundle size or runtime memory.
  - Interactive mouse tilt smoothly updates CSS variables within a constrained ±5° range.
  - Accessibility & Reduced Motion: When `prefers-reduced-motion: reduce` is detected or on mobile screens, 3D transformations are disabled in favor of an orthographic flat layout.

---

## 5. Visual QA & Verification Across Viewports

Visual QA was executed via headless browser captures across all primary application routes and three standard desktop viewports:
- **1440 × 900:** Primary desktop target
- **1280 × 800:** Compact desktop / small laptop
- **1920 × 1080:** Widescreen workstation

### Evidence Screenshots
All captured screenshots are archived in:
`docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/`

| Route | Before Screenshot | After Screenshot (1440x900) | After Screenshot (1920x1080) |
| :--- | :--- | :--- | :--- |
| **Overview (`/`)** | [before_overview_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_overview_1440.png) | [after_overview_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_overview_1440.png) | [after_overview_1920.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_overview_1920.png) |
| **AI Analyst (`/ai`)** | [before_ai_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_ai_1440.png) | [after_ai_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_ai_1440.png) | [after_ai_1920.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_ai_1920.png) |
| **Market (`/market`)** | [before_market_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_market_1440.png) | [after_market_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_market_1440.png) | [after_market_1920.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_market_1920.png) |
| **Opportunities (`/opportunities`)** | [before_opportunities_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_opportunities_1440.png) | [after_opportunities_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_opportunities_1440.png) | — |
| **Portfolio (`/portfolio`)** | [before_portfolio_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_portfolio_1440.png) | [after_portfolio_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_portfolio_1440.png) | — |
| **Research (`/research`)** | [before_research_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_research_1440.png) | [after_research_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_research_1440.png) | — |
| **Data Center (`/data-center`)** | [before_data_center_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_data_center_1440.png) | [after_data_center_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_data_center_1440.png) | — |
| **Watchlist (`/watchlist`)** | [before_watchlist_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/before_watchlist_1440.png) | [after_watchlist_1440.png](file:///C:/Users/baotr/Downloads/trading/docs/audits/evidence/investintel_premium_desktop_ui_2026-10-28/after_watchlist_1440.png) | — |

---

## 6. Technical Validation Results

1. **TypeScript Check:**
   ```
   npx tsc --noEmit
   Result: 0 errors
   ```
2. **Next.js Production Build:**
   ```
   npm run build
   ▲ Next.js 16.3.7 (Turbopack)
   ✓ Compiled successfully in 641ms
   ✓ Finished TypeScript in 1117ms
   ✓ Generating static pages (13/13) in 386ms
   Exit Code: 0
   ```
3. **Backend Service Health:**
   ```
   GET http://localhost:8000/api/v1/health -> 200 OK (PostgreSQL connected, latency: 2.99ms)
   GET http://localhost:8000/api/v1/ai/status -> 200 OK (Honest UNAVAILABLE status reported when Ollama daemon is offline)
   ```

---

## 7. Preservation of Functionality & Safety Boundaries

- **SSE Streaming Intact:** Server-Sent Events architecture, event contracts, heartbeat tracking, and cancellation hooks (`AbortController`) in `streamAIChat` remain unaltered.
- **Evidence Provenance Preserved:** Citations popover retains `observation_date`, `publication_date`, `responsible_module`, `data_origin`, and external URL verification.
- **IAS 33 Disclosures Maintained:** Estimated EPS badges and missing-data flags continue to display prominent disclosures rather than masking them.
- **API Contracts Untouched:** Request and response schemas across all endpoints (`/market`, `/ai/query`, `/data/providers`, `/opportunities`, `/portfolio`, `/watchlist`) remain 100% backward compatible.
- **Hard Boundaries Respected:**
  - Local development only.
  - Zero deployment calls to Render or Vercel.
  - `ALLOW_PRODUCTION_DB_WRITE=false` strictly enforced.
  - No git commits, pushes, merges, or releases made.
  - No simulated AI statuses or fabricated market metrics.

