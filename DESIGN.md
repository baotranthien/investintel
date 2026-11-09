---
name: InvestIntel
description: Institutional-grade financial workstation combining Swiss typographic discipline with Apple-inspired spatial materials.
colors:
  primary: "#1D1D1F"
  neutral-bg: "#F5F5F7"
  surface: "#FFFFFF"
  surface-card: "#FFFFFF"
  surface-sidebar: "#FAFAFC"
  surface-muted: "#F2F2F7"
  ink: "#1D1D1F"
  ink-secondary: "#475569"
  ink-muted: "#52525B"
  line: "rgba(0, 0, 0, 0.08)"
  line-strong: "rgba(0, 0, 0, 0.16)"
  positive: "#15803D"
  positive-soft: "#DCFCE7"
  negative: "#DC2626"
  negative-soft: "#FEE2E2"
  warning: "#B45309"
  warning-soft: "#FEF3C7"
  accent-blue: "#2563EB"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif"
    fontSize: "2rem"
    fontWeight: 700
    lineHeight: 1.15
    letterSpacing: "-0.03em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Inter', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 650
    lineHeight: 1.25
    letterSpacing: "-0.02em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "-0.01em"
  caption:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Inter', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0em"
  mono:
    fontFamily: "'SF Mono', 'JetBrains Mono', 'Roboto Mono', Menlo, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "0.02em"
rounded:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  full: "9999px"
spacing:
  2xs: "4px"
  xs: "8px"
  sm: "12px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  2xl: "48px"
components:
  card:
    backgroundColor: "{colors.surface-card}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "20px"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#FFFFFF"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
---

# InvestIntel Design System

## Overview
InvestIntel's visual language is tailored for high-stakes financial analysis and quantitative decision making. It operates in **Operate Mode**: prioritizing scanability, high data density, rock-solid hierarchy, typographic precision, and calm emotional restraint. It deliberately rejects decorative "AI slop" — no noisy gradients, no exaggerated neon halos, no faux pulsing dots, and no thick asymmetrical side borders on cards.

## Colors
The palette is built on high-contrast semantic neutrals paired with clear, non-neon financial indicators:
- **Ink Primary (`#1D1D1F`):** Deep charcoal for primary headings and prominent data values.
- **Ink Secondary (`#475569`):** Slate-600 ensuring crisp 6:1+ contrast against light surfaces (exceeding WCAG AA 4.5:1).
- **Ink Muted (`#52525B`):** Zinc-600 for supporting labels and timestamps, maintaining an unambiguous 5:1+ contrast floor.
- **Semantic Signals:**
  - **Positive (`#15803D`):** Deep forest emerald for gains, undervalued ratings, and passing quality checks.
  - **Negative (`#DC2626`):** Vibrant crimson for losses, overvalued states, and risk warnings.
  - **Warning (`#B45309`):** Amber gold for pending checks, transitional regimes, and cautions.
  - **Trust Accent (`#2563EB`):** Cobalt blue for links, selection indicators, and primary interaction points.

## Typography
Typography uses system native type stacks (`SF Pro Display`, `SF Pro Text`, `Inter`) tuned for financial data readability:
- **Strict 11px Functional Floor:** No interactive or content-bearing UI element (nav item, badge, metadata, table cell) shall fall below 11px. Micro-labels must be at least 11px (11.5px preferred).
- **Tabular Numerics:** All currency, prices, index points, P/E ratios, and percentages must declare `font-variant-numeric: tabular-nums` or `tabular-nums` class to eliminate column jitter.
- **Line Heights:** Body text maintains 1.5–1.6 line height for comfortable scanning; headings clamp to 1.15–1.25 for punchy optical density.

## Layout & Spatial Rhythm
- **8pt Base Grid:** Spatial tokens step rhythmically from `4px`, `8px`, `12px`, `16px`, `24px` to `32px`.
- **Card Containers:** Cards declare elevation once (via 1px subtle border or soft ambient shadow). No nested cards inside cards.
- **Responsive Flex/Grid:** Multi-column grids collapse gracefully: 1 column on mobile (<768px), 2 columns on tablet (768–1024px), 3–4 columns on workstation displays (1280px+).

## Elevation & Depth
- **Borders over Heavy Shadows:** Hairline borders (`1px solid var(--line)`) create clean containment without visual murkiness.
- **Ambient Shadows:** Diffused, zero-tint drop shadows (`0 1px 3px rgba(0,0,0,0.04)`) elevate interactive menus and modals without neon backglows.
- **Spatial Bento Tilt:** High-priority overview cards utilize subtle, spring-damped 2.5D perspective tilt ($\pm 3^\circ$) on hover with a soft specular radial spotlight, returning cleanly to $0^\circ$.

## Shapes
- **Container Radii:** Standard card containers use `14px` or `16px` border-radius.
- **Interactive Controls:** Buttons, inputs, and select dropdowns use `8px` or `10px` radius.
- **Pills & Badges:** Reserved strictly for status badges, citation pills, and category chips using `9999px` full radius.

## Components
- **Citation Pills:** Footnote-styled pills referencing audited financial filings. Clicking a pill displays the provenance and exact source document.
- **Status Badges:** Compact, clear status indicators pairing a solid 6px indicator dot with high-contrast text. Never use decorative pulsing animations on static indicators.
- **3D Visualizers:** High-performance, demand-rendered Three.js components (`QuantCoreOrb3D`, `PortfolioTorus3D`, `MultiFactorCube3D`) with full Light/Dark mode parity and automatic power-saving pauses.

## Do's and Don'ts
- **DO:**
  - Enforce WCAG AA contrast (≥ 4.5:1) across every text node.
  - Keep interactive tap/click targets to a minimum of 44×44px (or adequate padding).
  - Use smooth exponential deceleration (`cubic-bezier(0.16, 1, 0.3, 1)`) for all state transitions.
  - Provide distinct, accessible `:focus-visible` outlines for keyboard navigators.
- **DON'T:**
  - **NO SIDE-TAB BORDERS:** Do not use 3px/4px colored `border-left` or `border-right` on cards as an AI decoration.
  - **NO UNDERSIZED TEXT:** Never use 8px, 9px, or 10px text for functional copy.
  - **NO BOUNCE/ELASTIC EASING:** Avoid spring bounce oscillations; decelerate smoothly.
  - **NO FAKE PULSING:** Do not attach continuous CSS pulsing animations to static state badges.
  - **NO NESTED CARDS:** Do not put `<article>` cards inside `<article>` cards; use clean dividers or list rows instead.

