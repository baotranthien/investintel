# InvestIntel — True Apple Daylight & Warm Neutral Minimalism Redesign Audit Report

- **Date:** 2026-10-28
- **Platform:** InvestIntel Desktop Financial Workstation (`http://localhost:3000`)
- **Backend API:** FastAPI Local Daemon (`http://localhost:8000`)
- **Design Philosophy:** True Apple Daylight / Warm Neutral Minimalism (Inspired by Apple Card, macOS System Settings, Apple Stocks on iPadOS, and Linear Minimalist UI)
- **Status:** PASS (Strict Light Neutral Palette, Clean Summary Strip, Decluttered Minimalist UX, 13/13 Next.js Routes Compiled, 0 TypeScript Errors)

---

## 1. Executive Summary & Design Transformation

This critical design revision eradicated the lingering "Dark / Cyan AI Dashboard" look (heavy `#0c0d10` OLED black, glowing cyan/sky borders `#2997ff`, and cluttered 3D wireframe boxes) and established **True Apple Daylight / Warm Neutral Minimalism**:

1. **Absolute Removal of Cyan, Neon Blue, and Pitch-Black Foundations:**
   - **App Canvas:** Replaced pitch black with **Apple Light Gray / Warm Stone (`#F5F5F7`)**.
   - **Elevated Surfaces:** Clean pure white (`#FFFFFF`) cards and panels paired with diffused ambient shadows (`0 2px 12px rgba(0, 0, 0, 0.03)`).
   - **Secondary Surfaces & Pills:** Soft stone silver (`#EFEFF4` / `#F2F2F7`).
   - **Hairline Borders:** Nearly invisible sub-pixel dividers (`1px solid rgba(0, 0, 0, 0.06)`). All neon glows and specular cyan insets have been eliminated.
   - **Typography Ink:** Replaced stark black with calm **Apple Charcoal (`#1D1D1F`)**, neutral gray secondary labels (`#6E6E73`), and muted captions (`#86868B`).
   - **Monochrome Accents:** Primary interactive buttons use solid **Charcoal `#1D1D1F`** with pure white text, transitioning to `#333336` on hover.

2. **Decluttered Minimalist UX (Elimination of "Boxes Inside Boxes"):**
   - **3D Tilt Removal:** Completely replaced the heavy 3D isometric tilt in `DimensionalMarketRadar` with a **Clean Market Summary Strip** — a flat, horizontal, elegant bar presenting `VNINDEX` and `VN30` levels, point changes, and a sleek bilateral advance/decline participation track.
   - **Whitespace Over Borders:** Removed excessive nested box borders across the Market, Opportunity, and Overview pages, using generous whitespace and subtle horizontal hairlines (`border-b: 1px solid rgba(0, 0, 0, 0.05)`).
   - **AI Analyst Editorial Flow:** Evolved the cramped two-column layout into a **Centered Editorial Reading Flow (`max-width: 880px`)** inspired by Apple Notes and the macOS ChatGPT app.
   - **Floating Prompt Bar:** Crafted an elevated pill/card with white background (`#FFFFFF`), rounded-2xl geometry (`border-radius: 20px`), subtle shadow, and a minimalist black submit button.
   - **Minimalist Chips & Stone Citations:** Replaced loud colored tags with soft stone pills (`bg-[#EFEFF4] text-[#1D1D1F] hover:bg-[#E5E5EA]`). Academic citation pills (`[E001]`) render as understated stone badges with provenance tooltips.
   - **Apple.com Spec-Style Fallback Tables:** Structured quantitative indicators as clean horizontal specification rows with left-aligned keys, right-aligned `tabular-nums` values, and zero vertical divider lines.

---

## 2. Visual Evidence & Captured Screenshots

All 13 high-resolution screenshot artifacts are archived in:
`docs/audits/evidence/investintel_apple_neutral_minimalism_2026-10-28/`

| Route | Viewport | Artifact Filename | Design Validation |
| :--- | :--- | :--- | :--- |
| **Overview** (`/`) | 1440×900 | `apple_daylight_overview_1440.png` | Warm Stone `#F5F5F7` canvas, clean `#FFFFFF` workflow bento, monochrome `#1D1D1F` refresh button. |
| **Overview** (`/`) | 1280×800 | `apple_daylight_overview_1280.png` | Compact desktop grid scaling with intact whitespace and tabular numerals. |
| **Overview** (`/`) | 1920×1080 | `apple_daylight_overview_1920.png` | Widescreen alignment with maximum width constraints preventing visual drift. |
| **Market** (`/market`) | 1440×900 | `apple_daylight_market_1440.png` | Flat horizontal Market Summary Strip, zero 3D tilt, subtle bilateral advance/decline track. |
| **Market** (`/market`) | 1280×800 | `apple_daylight_market_1280.png` | Clean benchmark indices and decluttered macro cards without box-in-box fatigue. |
| **Market** (`/market`) | 1920×1080 | `apple_daylight_market_1920.png` | Spacious institutional market telemetry with clean white cards on warm neutral canvas. |
| **AI Analyst** (`/ai`) | 1440×900 | `apple_daylight_ai_1440.png` | Centered 880px editorial flow, floating prompt pill, stone recommendation chips (`#EFEFF4`). |
| **AI Analyst** (`/ai`) | 1280×800 | `apple_daylight_ai_1280.png` | Responsive centered reading column with calm Apple Charcoal typography. |
| **AI Analyst** (`/ai`) | 1920×1080 | `apple_daylight_ai_1920.png` | Focused Apple Notes reading environment with ample side margins. |
| **Opportunities** (`/opportunities`) | 1440×900 | `apple_daylight_opportunities_1440.png` | Clean white table, subtle row hover, elimination of harsh dark backgrounds. |
| **Portfolio** (`/portfolio`) | 1440×900 | `apple_daylight_portfolio_1440.png` | Apple Charcoal action buttons, soft stone form inputs, clean position ledger. |
| **Data Center** (`/data-center`) | 1440×900 | `apple_daylight_data_center_1440.png` | Crisp provenance timestamps, clean provider status badges, zero cyan glows. |
| **Watchlist** (`/watchlist`) | 1440×900 | `apple_daylight_watchlist_1440.png` | Minimalist thesis cards, monochrome edit buttons, calm IAS 33 amber indicators. |

---

## 3. Technical Verification & Compilation

### A. Next.js Turbopack Production Build
- Command: `npm --prefix apps/web run build`
- Result: **13/13 static and dynamic routes compiled in 828ms**
- TypeScript Status: **0 errors, 100% clean check**

### B. Color Token Rigor & Purity Audit
- Grepped across all `.tsx`, `.ts`, and `.module.css` files for cyan/neon tokens (`#00d2ff`, `#00f2fe`, `#06b6d4`, `#00ffff`, `#2997ff`): **0 occurrences found**.
- Verified canvas base defaults to light warm stone (`#F5F5F7`), with pure white elevated surfaces (`#FFFFFF`) and charcoal typography (`#1D1D1F`).

### C. Backend Regression Integrity
- Test suite across `tests/`: **316 / 316 passed (100% pass rate)**.
- Database protection: `ALLOW_PRODUCTION_DB_WRITE=false` strictly preserved.

