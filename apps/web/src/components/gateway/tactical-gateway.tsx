"use client";

import React, {
  useCallback,
  useEffect,
  useRef,
  useState,
  useMemo,
  useSyncExternalStore,
  type JSX,
} from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import {
  motion,
  useMotionTemplate,
  useMotionValue,
  useMotionValueEvent,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
} from "framer-motion";
import { getOpportunityScanner, type OpportunityFilters } from "@/lib/api";
import { useLocale, type AppLocale } from "@/lib/i18n";
import { useTheme, type EffectiveTheme } from "@/lib/theme";
import LanguageToggle from "@/components/language-toggle";
import ThemeToggle from "@/components/theme-toggle";
import styles from "./tactical-gateway.module.css";

export interface TacticalGatewayStock {
  symbol: string;
  name?: string;
  score: number;
  upside?: string;
  regime?: string;
}

export interface TacticalGatewayProps {
  topStocks?: TacticalGatewayStock[];
  children?: React.ReactNode;
}

const DEFAULT_TOP_STOCKS: TacticalGatewayStock[] = [
  { symbol: "CTG", name: "VietinBank", score: 88.5, upside: "+18.2%", regime: "GROWTH" },
  { symbol: "SIP", name: "Saigon VRG Investment", score: 86.4, upside: "+36.9%", regime: "VALUE" },
  { symbol: "FPT", name: "FPT Corp", score: 84.1, upside: "+22.5%", regime: "MOMENTUM" },
];

const DEFAULT_OPP_FILTERS: OpportunityFilters = {
  universe: "VN100",
  horizon: "MEDIUM_TERM",
  sector: "",
  scoreMin: "",
  riskMax: "",
  confidence: "",
  factor: "",
  valuationStatus: "",
};

function getMilestoneMeta(num: string, locale: AppLocale): { layer: string; metric: string } {
  const isEn = locale === "en";
  const meta: Record<string, { vi: [string, string]; en: [string, string] }> = {
    "06": { vi: ["RỦI RO 3D", "VaR 95%"], en: ["3D RISK", "VaR 95%"] },
    "05": { vi: ["TRỢ LÝ AI", "14 CÔNG CỤ"], en: ["AI ANALYST", "14 TOOLS"] },
    "04": { vi: ["TÍN HIỆU", "TOP 3 VN100"], en: ["SIGNALS", "TOP 3 VN100"] },
    "03": { vi: ["MÔ HÌNH", "7 NHÂN TỐ"], en: ["MODELS", "7 FACTORS"] },
    "02": { vi: ["CHUẨN HÓA", "IAS 33"], en: ["NORMALIZE", "IAS 33"] },
    "01": { vi: ["DỮ LIỆU GỐC", "3 SÀN"], en: ["RAW DATA", "3 EXCHANGES"] },
  };
  const entry = meta[num];
  if (!entry) return { layer: "", metric: "" };
  const [layer, metric] = isEn ? entry.en : entry.vi;
  return { layer, metric };
}

const LAYER_NUMBERS = ["06", "05", "04", "03", "02", "01"] as const;

const PIPELINE_PATH_D =
  "M 720 0 L 720 40 C 720 125, 912 160, 892 275 C 872 390, 555 375, 570 485 C 585 595, 905 605, 880 735 C 855 865, 530 915, 560 1050 C 581 1145, 720 1150, 720 1245 L 720 1420";

const DEFAULT_SVG_WAYPOINTS: WaypointMarker[] = [
  { num: "06", x: 891, y: 270, svgLenFrac: 0.16 },
  { num: "05", x: 582, y: 460, svgLenFrac: 0.31 },
  { num: "04", x: 830, y: 650, svgLenFrac: 0.45 },
  { num: "03", x: 838, y: 810, svgLenFrac: 0.58 },
  { num: "02", x: 585, y: 990, svgLenFrac: 0.72 },
  { num: "01", x: 660, y: 1155, svgLenFrac: 0.84 },
];

// Native nose vector in SVG (24, 46) relative to twin-nozzle midpoint (253, 159.5) points at -153.63 deg.
const SVG_NOSE_DEG = (Math.atan2(46 - 159.5, 24 - 253) * 180) / Math.PI;

interface CardObstacleBox {
  left: number;
  right: number;
  top: number;
  bottom: number;
}

interface FlightAnchor {
  p: number;
  x: number;
  y: number;
  scale: number;
  engine: number;
  dock: number;
  spineFrac: number;
}

interface WaypointMarker {
  num: string;
  x: number;
  y: number;
  svgLenFrac: number;
}

interface FlightTrackData {
  stops: number[];
  xs: number[];
  ys: number[];
  rotatesDown: number[];
  rotatesUp: number[];
  scales: number[];
  engines: number[];
  docks: number[];
  spineProgress: number[];
  layerThresholds: number[];
  dockThreshold: number;
  waypoints: WaypointMarker[];
  dockingCenter: { x: number; y: number } | null;
  entryRampPath: string;
  entryRampStart: { x: number; y: number } | null;
}

function clampNum(v: number, min: number, max: number): number {
  return v < min ? min : v > max ? max : v;
}

function smoothStep(edge0: number, edge1: number, x: number): number {
  const t = clampNum((x - edge0) / Math.max(0.0001, edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
}

function normalizeAngleNear(angle: number, anchor: number): number {
  let a = angle;
  while (a - anchor > 180) a -= 360;
  while (a - anchor < -180) a += 360;
  return a;
}

function centripetalCatmullRom2D(
  p0x: number,
  p0y: number,
  p1x: number,
  p1y: number,
  p2x: number,
  p2y: number,
  p3x: number,
  p3y: number,
  u: number
): { x: number; y: number } {
  const segTime = (ax: number, ay: number, bx: number, by: number): number =>
    Math.max(1e-3, Math.pow(Math.hypot(bx - ax, by - ay), 0.5));

  const t0 = 0;
  const t1 = t0 + segTime(p0x, p0y, p1x, p1y);
  const t2 = t1 + segTime(p1x, p1y, p2x, p2y);
  const t3 = t2 + segTime(p2x, p2y, p3x, p3y);
  const t = t1 + clampNum(u, 0, 1) * (t2 - t1);

  const lerpPt = (
    ax: number,
    ay: number,
    bx: number,
    by: number,
    ta: number,
    tb: number
  ): { x: number; y: number } => {
    const w = (t - ta) / Math.max(1e-4, tb - ta);
    return { x: ax + (bx - ax) * w, y: ay + (by - ay) * w };
  };

  const a1 = lerpPt(p0x, p0y, p1x, p1y, t0, t1);
  const a2 = lerpPt(p1x, p1y, p2x, p2y, t1, t2);
  const a3 = lerpPt(p2x, p2y, p3x, p3y, t2, t3);
  const b1 = lerpPt(a1.x, a1.y, a2.x, a2.y, t0, t2);
  const b2 = lerpPt(a2.x, a2.y, a3.x, a3.y, t1, t3);
  return lerpPt(b1.x, b1.y, b2.x, b2.y, t1, t2);
}

function pushSampleOutsideObstacles(
  x: number,
  y: number,
  halfW: number,
  halfH: number,
  obstacles: CardObstacleBox[],
  minX: number,
  maxX: number
): number {
  let nextX = x;
  for (let i = 0; i < obstacles.length; i++) {
    const ob = obstacles[i];
    const exLeft = ob.left - halfW;
    const exRight = ob.right + halfW;
    const exTop = ob.top - halfH;
    const exBottom = ob.bottom + halfH;
    if (y > exTop && y < exBottom && nextX > exLeft && nextX < exRight) {
      const canGoLeft = exLeft >= minX;
      const canGoRight = exRight <= maxX;
      if (canGoLeft && canGoRight) {
        nextX = Math.abs(nextX - exLeft) <= Math.abs(exRight - nextX) ? exLeft : exRight;
      } else if (canGoRight) {
        nextX = exRight;
      } else if (canGoLeft) {
        nextX = exLeft;
      }
    }
  }
  return clampNum(nextX, minX, maxX);
}

/** Sample control anchors through a 2D centripetal Catmull-Rom spline with multi-pass obstacle-safe smoothing. */
function buildDenseFlightTrack(
  anchors: FlightAnchor[],
  waypoints: WaypointMarker[],
  layerThresholds: number[],
  dockThreshold: number,
  dockingCenter: { x: number; y: number } | null,
  bounds: { minX: number; maxX: number; cruiseHalfW: number; cruiseHalfH: number },
  obstacles: CardObstacleBox[],
  entryRampPath = "",
  entryRampStart: { x: number; y: number } | null = null,
  roadLockStartP = 1.0
): FlightTrackData {
  const samples = 160;
  const stops: number[] = [];
  const xs: number[] = [];
  const ys: number[] = [];
  const scales: number[] = [];
  const engines: number[] = [];
  const docks: number[] = [];
  const spineProgress: number[] = [];

  const first = anchors[0];
  const second = anchors[Math.min(1, anchors.length - 1)];
  const last = anchors[anchors.length - 1];
  const prevLast = anchors[Math.max(0, anchors.length - 2)];
  const ghostStartX = first.x * 2 - second.x;
  const ghostStartY = first.y * 2 - second.y;
  const ghostEndX = last.x * 2 - prevLast.x;
  const ghostEndY = last.y * 2 - prevLast.y;

  for (let s = 0; s <= samples; s++) {
    const p = s / samples;
    stops.push(p);

    let seg = 0;
    while (seg < anchors.length - 2 && p > anchors[seg + 1].p) {
      seg++;
    }
    const a1 = anchors[seg];
    const a2 = anchors[Math.min(seg + 1, anchors.length - 1)];
    const a0 = seg > 0 ? anchors[seg - 1] : { ...a1, x: ghostStartX, y: ghostStartY };
    const a3 = seg + 2 < anchors.length ? anchors[seg + 2] : { ...a2, x: ghostEndX, y: ghostEndY };

    const span = Math.max(0.0001, a2.p - a1.p);
    const u = clampNum((p - a1.p) / span, 0, 1);
    const smoothU = u * u * (3 - 2 * u);

    const pt2D = centripetalCatmullRom2D(a0.x, a0.y, a1.x, a1.y, a2.x, a2.y, a3.x, a3.y, u);
    const scaleVal = a1.scale + (a2.scale - a1.scale) * smoothU;
    const onRoadLocked = p >= roadLockStartP && p <= 0.915;

    const deflectedX =
      s > 2 && s < samples - 2 && obstacles.length > 0 && !onRoadLocked
        ? pushSampleOutsideObstacles(
          pt2D.x,
          pt2D.y,
          bounds.cruiseHalfW + 8,
          bounds.cruiseHalfH + 6,
          obstacles,
          bounds.minX,
          bounds.maxX
        )
        : clampNum(pt2D.x, bounds.minX, bounds.maxX);

    xs.push(deflectedX);
    ys.push(pt2D.y);
    scales.push(scaleVal);
    engines.push(a1.engine + (a2.engine - a1.engine) * smoothU);
    docks.push(a1.dock + (a2.dock - a1.dock) * smoothU);
    spineProgress.push(a1.spineFrac + (a2.spineFrac - a1.spineFrac) * u);
  }

  // Preserve Desktop road-locked bends while gently relaxing off-road obstacle deflections
  const smoothPasses = obstacles.length > 0 ? 3 : 2;
  for (let pass = 0; pass < smoothPasses; pass++) {
    const nextXs = xs.slice();
    const nextYs = ys.slice();
    for (let s = 3; s < samples - 2; s++) {
      const onRoadLocked = stops[s] >= roadLockStartP && stops[s] <= 0.915;
      if (onRoadLocked) {
        if (pass === 0) {
          nextXs[s] = clampNum(xs[s - 1] * 0.12 + xs[s] * 0.76 + xs[s + 1] * 0.12, bounds.minX, bounds.maxX);
          const avgY = ys[s - 1] * 0.12 + ys[s] * 0.76 + ys[s + 1] * 0.12;
          nextYs[s] = clampNum(avgY, nextYs[s - 1] + 1, ys[s + 1] - 1);
        }
        continue;
      }

      const avgX = xs[s - 1] * 0.24 + xs[s] * 0.52 + xs[s + 1] * 0.24;
      const avgY = ys[s - 1] * 0.2 + ys[s] * 0.6 + ys[s + 1] * 0.2;
      const boundedY = clampNum(avgY, nextYs[s - 1] + 1, ys[s + 1] - 1);
      nextYs[s] = boundedY;
      nextXs[s] =
        obstacles.length > 0
          ? pushSampleOutsideObstacles(
            avgX,
            boundedY,
            bounds.cruiseHalfW + 6,
            bounds.cruiseHalfH + 5,
            obstacles,
            bounds.minX,
            bounds.maxX
          )
          : clampNum(avgX, bounds.minX, bounds.maxX);
    }
    for (let s = 3; s < samples - 2; s++) {
      xs[s] = nextXs[s];
      ys[s] = nextYs[s];
    }
  }

  // Compute local tangent angles along 160 samples and filter smoothly for true road banking
  const rawDownTrack: number[] = [];
  const rawUpTrack: number[] = [];
  for (let idx = 0; idx <= samples; idx++) {
    const prev = Math.max(0, idx - 2);
    const next = Math.min(samples, idx + 2);
    const dx = xs[next] - xs[prev];
    const dy = Math.max(ys[next] - ys[prev], 6);

    const headingDownDeg = (Math.atan2(dy, dx) * 180) / Math.PI;
    rawDownTrack.push(clampNum(normalizeAngleNear(headingDownDeg - SVG_NOSE_DEG, -114), -166, -62));

    const headingUpDeg = (Math.atan2(-dy, -dx) * 180) / Math.PI;
    rawUpTrack.push(clampNum(normalizeAngleNear(headingUpDeg - SVG_NOSE_DEG, 66), 14, 118));
  }

  for (let pass = 0; pass < 3; pass++) {
    const dCopy = rawDownTrack.slice();
    const uCopy = rawUpTrack.slice();
    for (let idx = 1; idx < samples; idx++) {
      dCopy[idx] = rawDownTrack[idx - 1] * 0.25 + rawDownTrack[idx] * 0.5 + rawDownTrack[idx + 1] * 0.25;
      uCopy[idx] = rawUpTrack[idx - 1] * 0.25 + rawUpTrack[idx] * 0.5 + rawUpTrack[idx + 1] * 0.25;
    }
    for (let idx = 1; idx < samples; idx++) {
      rawDownTrack[idx] = dCopy[idx];
      rawUpTrack[idx] = uCopy[idx];
    }
  }

  const rotatesDown: number[] = [];
  const rotatesUp: number[] = [];
  for (let idx = 0; idx <= samples; idx++) {
    const p = stops[idx];
    const rawDown = rawDownTrack[idx];
    const rawUp = rawUpTrack[idx];

    let downAngle = rawDown;
    if (p <= 0.005) {
      downAngle = 0;
    } else if (p < 0.095) {
      downAngle = rawDown * smoothStep(0.005, 0.095, p);
    } else if (p > 0.89) {
      const kDock = smoothStep(0.89, 1.0, p);
      downAngle = rawDown * (1 - kDock) - 22 * kDock;
    }
    rotatesDown.push(downAngle);

    let upAngle = rawUp;
    if (p <= 0.005) {
      upAngle = 0;
    } else if (p < 0.105) {
      upAngle = rawUp * smoothStep(0.005, 0.105, p);
    } else if (p > 0.955) {
      const kDock = smoothStep(0.955, 1.0, p);
      upAngle = rawUp * (1 - kDock) - 22 * kDock;
    }
    rotatesUp.push(upAngle);
  }

  return {
    stops,
    xs,
    ys,
    rotatesDown,
    rotatesUp,
    scales,
    engines,
    docks,
    spineProgress,
    layerThresholds,
    dockThreshold,
    waypoints,
    dockingCenter,
    entryRampPath,
    entryRampStart,
  };
}

/** Find SVG path length whose Y matches targetSvgY inside non-uniform winding conduit. */
function findPathPointAtY(
  pathEl: SVGPathElement,
  totalLen: number,
  targetSvgY: number
): { x: number; y: number; frac: number } {
  const target = clampNum(targetSvgY, 0, 1500);
  let lo = 0;
  let hi = totalLen;
  for (let iter = 0; iter < 16; iter++) {
    const mid = (lo + hi) * 0.5;
    const pt = pathEl.getPointAtLength(mid);
    if (pt.y < target) {
      lo = mid;
    } else {
      hi = mid;
    }
  }
  const bestLen = (lo + hi) * 0.5;
  const pt = pathEl.getPointAtLength(bestLen);
  return {
    x: pt.x,
    y: pt.y,
    frac: totalLen > 0 ? clampNum(bestLen / totalLen, 0, 1) : 0,
  };
}

function createFallbackTrack(): FlightTrackData {
  const anchors: FlightAnchor[] = [
    { p: 0.0, x: 1200, y: 720, scale: 1, engine: 0.58, dock: 0, spineFrac: 0 },
    { p: 0.07, x: 1090, y: 830, scale: 0.68, engine: 0.78, dock: 0, spineFrac: 0.02 },
    { p: 0.14, x: 1065, y: 1005, scale: 0.42, engine: 0.8, dock: 0, spineFrac: 0.04 },
    { p: 0.24, x: 760, y: 1240, scale: 0.42, engine: 0.82, dock: 0, spineFrac: 0.16 },
    { p: 0.42, x: 820, y: 1580, scale: 0.42, engine: 0.82, dock: 0, spineFrac: 0.42 },
    { p: 0.62, x: 720, y: 1960, scale: 0.42, engine: 0.8, dock: 0, spineFrac: 0.68 },
    { p: 0.82, x: 620, y: 2320, scale: 0.42, engine: 0.64, dock: 0.1, spineFrac: 0.9 },
    { p: 1.0, x: 720, y: 2480, scale: 0.39, engine: 0.2, dock: 1, spineFrac: 1 },
  ];
  return buildDenseFlightTrack(
    anchors,
    DEFAULT_SVG_WAYPOINTS,
    [0.24, 0.38, 0.5, 0.62, 0.74, 0.85],
    0.92,
    null,
    { minX: 90, maxX: 1350, cruiseHalfW: 65, cruiseHalfH: 43 },
    []
  );
}

const FALLBACK_FLIGHT_TRACK = createFallbackTrack();

export function TacticalGateway({
  topStocks,
}: TacticalGatewayProps): JSX.Element | null {
  const router = useRouter();
  const { locale, t } = useLocale();
  const { effectiveTheme } = useTheme();
  const mounted = useSyncExternalStore(
    () => () => { },
    () => true,
    () => false
  );
  const [isGatewayOpen, setIsGatewayOpen] = useState(false);
  const [isBreaching, setIsBreaching] = useState(false);
  const [reopenKey, setReopenKey] = useState(0);
  const [fetchedStocks, setFetchedStocks] = useState<TacticalGatewayStock[]>(DEFAULT_TOP_STOCKS);
  const stocks = useMemo(
    () => (topStocks && topStocks.length > 0 ? topStocks : fetchedStocks),
    [topStocks, fetchedStocks]
  );

  const triggerBreach = useCallback(
    (targetRoute?: string) => {
      if (isBreaching) return;
      setIsBreaching(true);

      if (typeof window !== "undefined") {
        document.documentElement.removeAttribute("data-gateway-active");
        window.localStorage.setItem("investintel:gateway:connected", "true");
        window.sessionStorage.setItem("investintel:gateway:connected", "true");
        const url = new URL(window.location.href);
        if (url.searchParams.has("gateway") || url.searchParams.has("scrolly")) {
          url.searchParams.delete("gateway");
          url.searchParams.delete("scrolly");
          window.history.replaceState({}, "", url.pathname + (url.search ? url.search : ""));
        }
      }

      setTimeout(() => {
        setIsGatewayOpen(false);
        setIsBreaching(false);
        if (targetRoute) {
          router.push(targetRoute);
        }
      }, 420);
    },
    [isBreaching, router]
  );

  // Sync top opportunity stocks so Card 04 reflects live signals
  useEffect(() => {
    if (topStocks && topStocks.length > 0) return;
    let active = true;
    getOpportunityScanner(DEFAULT_OPP_FILTERS)
      .then((data) => {
        if (!active) return;
        if (data?.results && data.results.length > 0) {
          const sorted = [...data.results]
            .sort((a, b) => (b.opportunity_score ?? 0) - (a.opportunity_score ?? 0))
            .slice(0, 3)
            .map((o) => ({
              symbol: o.symbol,
              name: o.name ?? o.symbol,
              score: Math.round(o.opportunity_score ?? 80),
              upside: o.margin_of_safety ? `+${(o.margin_of_safety * 100).toFixed(1)}%` : "+20.0%",
              regime: o.valuation_status ?? "QUANT",
            }));
          setFetchedStocks(sorted);
        }
      })
      .catch(() => { });
    return () => {
      active = false;
    };
  }, [topStocks]);

  // Initialize gateway visibility from localStorage + sessionStorage + query param + custom event
  useEffect(() => {
    if (typeof window === "undefined") return;

    const url = new URL(window.location.href);
    const hasForceParam =
      url.searchParams.get("gateway") === "1" || url.searchParams.get("scrolly") === "1";
    const localConnected = window.localStorage.getItem("investintel:gateway:connected") === "true";
    const sessionConnected = window.sessionStorage.getItem("investintel:gateway:connected") === "true";
    const hasConnected = localConnected || sessionConnected;

    const shouldOpen = hasForceParam || !hasConnected;
    if (hasForceParam) {
      window.localStorage.removeItem("investintel:gateway:connected");
      window.sessionStorage.removeItem("investintel:gateway:connected");
      url.searchParams.delete("gateway");
      url.searchParams.delete("scrolly");
      window.history.replaceState({}, "", url.pathname + (url.search ? url.search : ""));
    }

    if (shouldOpen) {
      document.documentElement.setAttribute("data-gateway-active", "true");
    } else {
      document.documentElement.removeAttribute("data-gateway-active");
    }

    const initRaf = requestAnimationFrame(() => {
      setIsGatewayOpen(shouldOpen);
    });

    const handleReopen = () => {
      window.localStorage.removeItem("investintel:gateway:connected");
      window.sessionStorage.removeItem("investintel:gateway:connected");
      document.documentElement.setAttribute("data-gateway-active", "true");
      setIsBreaching(false);
      setIsGatewayOpen(true);
      setReopenKey((k) => k + 1);
    };

    window.addEventListener("investintel:open-gateway", handleReopen);
    return () => {
      cancelAnimationFrame(initRaf);
      window.removeEventListener("investintel:open-gateway", handleReopen);
    };
  }, []);

  // ESC closes gateway back into workspace
  useEffect(() => {
    if (!isGatewayOpen) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        triggerBreach();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [isGatewayOpen, triggerBreach]);

  if (!mounted || !isGatewayOpen) {
    return null;
  }

  return createPortal(
    <TacticalGatewayExperience
      key={reopenKey}
      isBreaching={isBreaching}
      stocks={stocks}
      locale={locale}
      t={t}
      effectiveTheme={effectiveTheme}
      onBreach={triggerBreach}
    />,
    document.body
  );
}

interface TacticalGatewayExperienceProps {
  isBreaching: boolean;
  stocks: TacticalGatewayStock[];
  locale: AppLocale;
  t: (vi: string, en: string) => string;
  effectiveTheme: EffectiveTheme;
  onBreach: (targetRoute?: string) => void;
}

function TacticalGatewayExperience({
  isBreaching,
  stocks,
  locale,
  t,
  effectiveTheme,
  onBreach,
}: TacticalGatewayExperienceProps): JSX.Element {
  const isLight = effectiveTheme === "light";
  const geo = useMemo(
    () =>
      isLight
        ? {
          baseBg: "#F4F6FA",
          sphereBase: "#E2E8F2",
          facet1: "#EAEFF7",
          facet2: "#DDE5F2",
          facet3: "#E4EBF5",
          facet4: "#D6DFF0",
          facet5: "#EDF2F8",
          facet6: "#D9E1EE",
          facet7: "#CFD8E6",
          facet8: "#CBD5E1",
          ringFill: "#FFFFFF",
          ringArm: "#CBD5E1",
          stroke: "#CBD5E1",
          strokeSubtle: "#94A3B8",
          accent: "#6355E8",
          accentBright: "#4F46E5",
          accentLight: "#818CF8",
          accentEdgeSoft: "rgba(99, 85, 232, 0.24)",
          accentEdgeMid: "rgba(99, 85, 232, 0.42)",
          accentEdgeStrong: "rgba(99, 85, 232, 0.62)",
          beaconBright: "#6355E8",
          coreBright: "#FFFFFF",
          coreChamber: "#E0E7FF",
        }
        : {
          baseBg: "#101522",
          sphereBase: "#131928",
          facet1: "#1A2133",
          facet2: "#1F273B",
          facet3: "#1D2437",
          facet4: "#232B42",
          facet5: "#262E48",
          facet6: "#151B2A",
          facet7: "#131926",
          facet8: "#111623",
          ringFill: "#191F2D",
          ringArm: "#2A334D",
          stroke: "#292F40",
          strokeSubtle: "#292F40",
          accent: "#9A8CFF",
          accentBright: "#C5BDFF",
          accentLight: "#C5BDFF",
          accentEdgeSoft: "rgba(154, 140, 255, 0.22)",
          accentEdgeMid: "rgba(154, 140, 255, 0.45)",
          accentEdgeStrong: "rgba(154, 140, 255, 0.62)",
          beaconBright: "#E6EAF2",
          coreBright: "#E6EAF2",
          coreChamber: "#232B45",
        },
    [isLight]
  );
  const prefersReducedMotion = useReducedMotion() ?? false;

  const containerRef = useRef<HTMLDivElement>(null);
  const contentRootRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const heroSectionRef = useRef<HTMLElement>(null);
  const heroPanelRef = useRef<HTMLDivElement>(null);
  const planetParallaxRef = useRef<HTMLDivElement>(null);
  const moonParallaxRef = useRef<HTMLDivElement>(null);
  const asteroidParallaxRef = useRef<HTMLDivElement>(null);
  const roadmapSectionRef = useRef<HTMLElement>(null);
  const valleyHeaderRef = useRef<HTMLDivElement>(null);
  const pipelinePathRef = useRef<SVGPathElement>(null);
  const shipRigRef = useRef<HTMLDivElement>(null);
  const portalRef = useRef<HTMLDivElement>(null);
  const reticleRef = useRef<HTMLDivElement>(null);
  const cardSlotRefs = useRef<(HTMLDivElement | null)[]>([null, null, null, null, null, null]);
  const stemNodeRefs = useRef<(HTMLSpanElement | null)[]>([null, null, null, null, null, null]);

  const scrollRafRef = useRef<number>(0);
  const headerScrolledRef = useRef<boolean>(false);
  const prevScrollProgressRef = useRef<number>(0);
  const scrollAccumRef = useRef<number>(0);
  const targetProgressRef = useRef<number>(0);
  const flightPosRef = useRef<number>(0);
  const flightVelRef = useRef<number>(0);
  const flightRafRef = useRef<number>(0);

  const [flightTrack, setFlightTrack] = useState<FlightTrackData>(FALLBACK_FLIGHT_TRACK);
  // -1 = hero/pre-pipeline, 0..5 = layer 06..01 active, 6 = terminal docked
  const [activeStage, setActiveStage] = useState<number>(-1);
  const activeStageRef = useRef<number>(-1);

  // Measure rendered hero, SVG conduit curves, banner boxes & terminal portal into collision-free spline
  const measureFlightTrack = useCallback(() => {
    const scrollEl = containerRef.current;
    const rootEl = contentRootRef.current;
    const heroEl = heroSectionRef.current;
    const valleyEl = roadmapSectionRef.current;
    const pathEl = pipelinePathRef.current;
    const rigEl = shipRigRef.current;
    const portalEl = portalRef.current;
    if (!scrollEl || !rootEl || !heroEl || !valleyEl || !pathEl || !rigEl || !portalEl) return;

    const rootRect = rootEl.getBoundingClientRect();
    const heroRect = heroEl.getBoundingClientRect();
    const heroPanelRect = heroPanelRef.current?.getBoundingClientRect();
    const valleyRect = valleyEl.getBoundingClientRect();
    const valleyHeaderRect = valleyHeaderRef.current?.getBoundingClientRect();
    const portalRect = portalEl.getBoundingClientRect();
    const reticleRect = reticleRef.current?.getBoundingClientRect() ?? portalRect;

    const rootW = Math.max(320, rootRect.width);
    const heroH = Math.max(480, heroRect.height);
    const valleyLeft = valleyRect.left - rootRect.left;
    const valleyW = Math.max(320, valleyRect.width);
    const valleyTop = valleyRect.top - rootRect.top;
    const valleyH = Math.max(900, valleyRect.height);
    const viewH = Math.max(400, scrollEl.clientHeight || window.innerHeight);
    const maxScroll = Math.max(1, scrollEl.scrollHeight - viewH);
    const svgTotalLen = pathEl.getTotalLength();

    // Use unscaled element layout dimensions so scrolled scale/rotation transforms never corrupt rest geometry
    const shipW = Math.max(120, rigEl.offsetWidth || rigEl.getBoundingClientRect().width || 240);
    const shipH = Math.max(80, rigEl.offsetHeight || rigEl.getBoundingClientRect().height || 160);
    const isMobile = rootW <= 600;
    const isTablet = rootW <= 960;

    // Compact nimble size for weaving cleanly around pipeline banners and sitting comfortably inside the 80px road
    const cruiseScale = isMobile ? 0.36 : isTablet ? 0.41 : 0.385;
    const dockScale = isMobile ? 0.34 : isTablet ? 0.38 : 0.365;
    const cruiseHalfW = shipW * cruiseScale * 0.5;
    const cruiseHalfH = shipH * cruiseScale * 0.5;

    // Exact Hero bottom-right rest center matching static CSS layout with zero Hero panel overlap
    const rightPx = isMobile ? 6 : clampNum(rootW * 0.035, 12, 72);
    const bottomPx = isMobile ? 84 : isTablet ? 64 : 68;
    const restX = rootW - rightPx - shipW * 0.5;
    const restY = heroH - bottomPx - shipH * 0.5;

    const docYToProgress = (docY: number, vpBias = 0.48): number =>
      clampNum((docY - viewH * vpBias) / maxScroll, 0, 0.995);

    const svgXToDoc = (svgX: number): number => valleyLeft + (svgX / 1440) * valleyW;

    const obstacles: CardObstacleBox[] = [];
    if (heroPanelRect) {
      obstacles.push({
        left: heroPanelRect.left - rootRect.left,
        right: heroPanelRect.right - rootRect.left,
        top: heroPanelRect.top - rootRect.top,
        bottom: heroPanelRect.bottom - rootRect.top,
      });
    }

    const headerTopY = valleyHeaderRect ? valleyHeaderRect.top - rootRect.top : valleyTop + 48;
    const headerBottomY = valleyHeaderRect ? valleyHeaderRect.bottom - rootRect.top : valleyTop + 170;
    const headerRightX = valleyHeaderRect ? valleyHeaderRect.right - rootRect.left : rootW * 0.67;
    if (valleyHeaderRect) {
      obstacles.push({
        left: valleyHeaderRect.left - rootRect.left,
        right: valleyHeaderRect.right - rootRect.left,
        top: headerTopY,
        bottom: headerBottomY,
      });
    }

    // Open right corridor alongside "From Raw Data to Decision" header banner
    const edgePadX = isMobile ? 8 : isTablet ? 16 : 22;
    const rightLaneX = clampNum(
      headerRightX + cruiseHalfW + (isMobile ? 10 : isTablet ? 24 : 42),
      cruiseHalfW + edgePadX,
      rootW - cruiseHalfW - edgePadX
    );

    const measuredWaypoints: WaypointMarker[] = [];
    const layerAnchors: {
      x: number;
      y: number;
      rawP: number;
      spineFrac: number;
      cardBox: CardObstacleBox | null;
    }[] = [];

    for (let i = 0; i < LAYER_NUMBERS.length; i++) {
      const stemEl = stemNodeRefs.current[i];
      const slotEl = cardSlotRefs.current[i];
      const cardEl = slotEl?.querySelector("article");
      const cardRect = cardEl?.getBoundingClientRect();
      const fallbackWp = DEFAULT_SVG_WAYPOINTS[i];

      let stemDocY = valleyTop + (fallbackWp.y / 1600) * valleyH;
      if (stemEl) {
        const sr = stemEl.getBoundingClientRect();
        stemDocY = sr.top - rootRect.top + sr.height * 0.5;
      } else if (slotEl) {
        const cr = slotEl.getBoundingClientRect();
        stemDocY = cr.bottom - rootRect.top - 12;
      }

      let cardBox: CardObstacleBox | null = null;
      if (cardRect) {
        cardBox = {
          left: cardRect.left - rootRect.left,
          right: cardRect.right - rootRect.left,
          top: cardRect.top - rootRect.top,
          bottom: cardRect.bottom - rootRect.top,
        };
        obstacles.push(cardBox);
      }

      const targetSvgY = clampNum(((stemDocY - valleyTop) / valleyH) * 1600, 50, 1460);
      const pt = findPathPointAtY(pathEl, svgTotalLen, targetSvgY);

      measuredWaypoints.push({
        num: LAYER_NUMBERS[i],
        x: pt.x,
        y: pt.y,
        svgLenFrac: pt.frac,
      });

      const padSideX = cruiseHalfW + (isMobile ? 10 : isTablet ? 20 : 28);
      let spineDocX = svgXToDoc(pt.x);

      if (isMobile) {
        // Grouped in 2-layer banks (06-05 Left -> 04-03 Right -> 02-01 Left) so flight weaves in 2 slow S-waves
        const onRightRunway = i <= 1 || i >= 4;
        const gentleSway = i === 1 || i === 4 ? -4 : 0;
        spineDocX = onRightRunway
          ? rootW - cruiseHalfW - 10 + gentleSway
          : cruiseHalfW + 10 - gentleSway;
      } else if (isTablet && cardBox) {
        // Upper half glides smoothly down right channel (06-04), single graceful S-cross to left (03-01)
        const onRightFlank = i <= 2;
        const rightOpen = Math.min(rootW - cruiseHalfW - 14, cardBox.right + padSideX);
        const leftOpen = Math.max(cruiseHalfW + 14, cardBox.left - padSideX);
        const arcOffset = onRightFlank ? (2 - i) * 6 : (i - 3) * 6;
        spineDocX = onRightFlank ? rightOpen + arcOffset : leftOpen - arcOffset;
      } else if (cardBox) {
        // Desktop follows the exact SVG conduit curve wherever clear of cards
        if (spineDocX >= cardBox.left - padSideX && spineDocX <= cardBox.right + padSideX) {
          const rightRoom = rootW - cardBox.right;
          spineDocX =
            rightRoom >= cardBox.left
              ? Math.min(rootW - cruiseHalfW - 22, cardBox.right + padSideX)
              : Math.max(cruiseHalfW + 22, cardBox.left - padSideX);
        }
      }

      const anchorY = cardBox ? (cardBox.top + cardBox.bottom) * 0.5 : stemDocY - 12;
      layerAnchors.push({
        x: spineDocX,
        y: anchorY,
        rawP: docYToProgress(anchorY, 0.5),
        spineFrac: pt.frac,
        cardBox,
      });
    }

    // Terminal dock point cleanly centered just above End Portal & its rotating reticle
    const portalTop = portalRect.top - rootRect.top;
    const dockCenterX = reticleRect.left - rootRect.left + reticleRect.width * 0.5;
    const dockCenterY = portalTop - (isMobile ? 52 : isTablet ? 60 : 64);
    const dockEndFrac = findPathPointAtY(
      pathEl,
      svgTotalLen,
      clampNum(((portalTop - valleyTop) / valleyH) * 1600, 100, 1495)
    ).frac;
    const dockApproachFrac = findPathPointAtY(
      pathEl,
      svgTotalLen,
      clampNum(((dockCenterY - 46 - valleyTop) / valleyH) * 1600, 100, 1495)
    ).frac;

    const headerMidY = (headerTopY + headerBottomY) * 0.5;
    const rawTakeoffP = clampNum(docYToProgress(heroH * 0.88, 0.45), 0.04, 0.095);
    const rawHeaderPassP = clampNum(docYToProgress(headerMidY, 0.5), rawTakeoffP + 0.04, 0.17);
    const bridgeClearY = headerBottomY + cruiseHalfH + (isMobile ? 22 : 44);
    const rawBridgeP = clampNum(docYToProgress(bridgeClearY, 0.5), rawHeaderPassP + 0.035, 0.235);

    const mergeSvgY = clampNum(((headerBottomY + cruiseHalfH + 150 - valleyTop) / valleyH) * 1600, 275, 330);
    const mergePt = findPathPointAtY(pathEl, svgTotalLen, mergeSvgY);
    const mergeDocX = svgXToDoc(mergePt.x);
    const svgYToDoc = (svgY: number): number => valleyTop + (svgY / 1600) * valleyH;
    const mergeDocY = svgYToDoc(mergePt.y);

    const bridgeX = isMobile
      ? rightLaneX
      : isTablet
        ? clampNum(rightLaneX - (rightLaneX - layerAnchors[0].x) * 0.25, layerAnchors[0].x, rightLaneX)
        : clampNum(rightLaneX - (rightLaneX - mergeDocX) * 0.42, mergeDocX, rightLaneX);

    let entryRampPath = "";
    let entryRampStart: { x: number; y: number } | null = null;
    let rampCtrlPts: {
      startX: number;
      startY: number;
      ctrl1X: number;
      ctrl1Y: number;
      ctrl2X: number;
      ctrl2Y: number;
      endX: number;
      endY: number;
    } | null = null;
    if (!isMobile && !isTablet) {
      const docXToSvg = (docX: number) => clampNum((docX / Math.max(1, rootW)) * 1440, 0, 1440);
      const docYToSvg = (docY: number) => clampNum(((docY - valleyTop) / Math.max(1, valleyH)) * 1600, 0, 1600);
      const rampStartSvgX = docXToSvg(rightLaneX);
      const rampStartSvgY = docYToSvg(Math.max(valleyTop + 20, headerMidY));
      const rampEndSvgX = mergePt.x;
      const rampEndSvgY = mergePt.y;
      const rampDist = Math.hypot(rampEndSvgX - rampStartSvgX, rampEndSvgY - rampStartSvgY);
      const mLen = mergePt.frac * svgTotalLen;
      const pBefore = pathEl.getPointAtLength(Math.max(0, mLen - 12));
      const pAfter = pathEl.getPointAtLength(Math.min(svgTotalLen, mLen + 12));
      const tanLen = Math.hypot(pAfter.x - pBefore.x, pAfter.y - pBefore.y) || 1;
      const tx = (pAfter.x - pBefore.x) / tanLen;
      const ty = (pAfter.y - pBefore.y) / tanLen;
      const ctrl1X = rampStartSvgX;
      const ctrl1Y = clampNum(rampStartSvgY + rampDist * 0.44, 0, 1600);
      const ctrl2X = clampNum(rampEndSvgX - tx * rampDist * 0.42, 0, 1440);
      const ctrl2Y = clampNum(rampEndSvgY - ty * rampDist * 0.42, 0, 1600);
      entryRampStart = { x: rampStartSvgX, y: rampStartSvgY };
      entryRampPath = `M ${rampStartSvgX.toFixed(1)} ${rampStartSvgY.toFixed(1)} C ${ctrl1X.toFixed(1)} ${ctrl1Y.toFixed(1)}, ${ctrl2X.toFixed(1)} ${ctrl2Y.toFixed(1)}, ${rampEndSvgX.toFixed(1)} ${rampEndSvgY.toFixed(1)}`;
      rampCtrlPts = {
        startX: svgXToDoc(rampStartSvgX),
        startY: svgYToDoc(rampStartSvgY),
        ctrl1X: svgXToDoc(ctrl1X),
        ctrl1Y: svgYToDoc(ctrl1Y),
        ctrl2X: svgXToDoc(ctrl2X),
        ctrl2Y: svgYToDoc(ctrl2Y),
        endX: mergeDocX,
        endY: mergeDocY,
      };
    }

    const anchors: FlightAnchor[] = [
      { p: 0.0, x: restX, y: restY, scale: 1.0, engine: 0.58, dock: 0, spineFrac: 0 },
      {
        p: rawTakeoffP,
        x: restX + (rightLaneX - restX) * 0.46,
        y: heroH * 0.9,
        scale: isMobile ? 0.64 : 0.72,
        engine: 0.76,
        dock: 0,
        spineFrac: 0.015,
      },
      {
        p: rawHeaderPassP,
        x: rightLaneX,
        y: headerMidY,
        scale: cruiseScale,
        engine: 0.8,
        dock: 0,
        spineFrac: 0.03,
      },
    ];

    const computedLayerThresholds: number[] = [];
    let prevP = rawHeaderPassP;
    let roadLockStartP = 1.0;

    if (!isMobile && !isTablet && rampCtrlPts) {
      // Desktop: sample the exact on-ramp Bezier then follow the full SVG road centerline cleanly
      roadLockStartP = rawHeaderPassP;
      const minXDesktop = Math.max(edgePadX + cruiseHalfW, 34);
      const maxXDesktop = Math.max(minXDesktop + 20, rootW - minXDesktop);
      const rawMergeP = clampNum(docYToProgress(mergeDocY, 0.5), rawHeaderPassP + 0.055, 0.245);
      const onRampSteps = 5;

      for (let s = 1; s <= onRampSteps; s++) {
        const u = s / onRampSteps;
        const inv = 1 - u;
        const bx =
          inv * inv * inv * rampCtrlPts.startX +
          3 * inv * inv * u * rampCtrlPts.ctrl1X +
          3 * inv * u * u * rampCtrlPts.ctrl2X +
          u * u * u * rampCtrlPts.endX;
        const by =
          inv * inv * inv * rampCtrlPts.startY +
          3 * inv * inv * u * rampCtrlPts.ctrl1Y +
          3 * inv * u * u * rampCtrlPts.ctrl2Y +
          u * u * u * rampCtrlPts.endY;
        const pHere = rawHeaderPassP + (rawMergeP - rawHeaderPassP) * u;
        anchors.push({
          p: pHere,
          x: clampNum(bx, minXDesktop, maxXDesktop),
          y: by,
          scale: cruiseScale,
          engine: 0.82,
          dock: 0,
          spineFrac: 0.03 + (mergePt.frac - 0.03) * u,
        });
      }

      prevP = rawMergeP;
      const roadSteps = 36;
      const roadStartFrac = clampNum(mergePt.frac, 0.06, 0.26);
      const roadEndFrac = clampNum(
        Math.max(dockApproachFrac, measuredWaypoints[measuredWaypoints.length - 1].svgLenFrac + 0.02),
        roadStartFrac + 0.15,
        0.97
      );
      const roadSamples: { frac: number; p: number }[] = [{ frac: roadStartFrac, p: rawMergeP }];

      for (let k = 1; k <= roadSteps; k++) {
        const t = k / roadSteps;
        const frac = roadStartFrac + (roadEndFrac - roadStartFrac) * t;
        const pt = pathEl.getPointAtLength(frac * svgTotalLen);
        const rawRoadX = svgXToDoc(pt.x);
        const roadY = svgYToDoc(pt.y);
        const safeX = pushSampleOutsideObstacles(
          rawRoadX,
          roadY,
          cruiseHalfW + 2,
          cruiseHalfH + 2,
          obstacles,
          minXDesktop,
          maxXDesktop
        );
        const remaining = roadSteps - k;
        const maxAllowedHere = 0.915 - remaining * 0.009;
        const linearRoadP = rawMergeP + (0.895 - rawMergeP) * t;
        const docRoadP = docYToProgress(roadY, 0.5);
        const blendedP = linearRoadP * 0.68 + docRoadP * 0.32;
        const pHere = clampNum(Math.max(blendedP, prevP + 0.01), prevP + 0.008, maxAllowedHere);
        prevP = pHere;

        roadSamples.push({ frac, p: pHere });
        anchors.push({
          p: pHere,
          x: safeX,
          y: roadY,
          scale: cruiseScale,
          engine: k >= roadSteps - 1 ? 0.64 : 0.82,
          dock: k >= roadSteps - 1 ? 0.08 : 0,
          spineFrac: frac,
        });
      }

      for (let i = 0; i < measuredWaypoints.length; i++) {
        const targetFrac = measuredWaypoints[i].svgLenFrac;
        let wpP = roadSamples[roadSamples.length - 1].p;
        for (let s = 0; s < roadSamples.length - 1; s++) {
          if (targetFrac <= roadSamples[s + 1].frac) {
            const spanF = Math.max(0.0001, roadSamples[s + 1].frac - roadSamples[s].frac);
            const u = clampNum((targetFrac - roadSamples[s].frac) / spanF, 0, 1);
            wpP = roadSamples[s].p + (roadSamples[s + 1].p - roadSamples[s].p) * u;
            break;
          }
        }
        computedLayerThresholds.push(Math.max(rawHeaderPassP + 0.025, wpP - 0.042));
      }
    } else {
      // Tablet / Mobile: smooth card-clearance flanks with at most 1-2 sweeping S-crossings
      anchors.push({
        p: rawBridgeP,
        x: bridgeX,
        y: bridgeClearY,
        scale: cruiseScale,
        engine: 0.82,
        dock: 0,
        spineFrac: 0.055,
      });
      prevP = rawBridgeP + 0.038;
      let prevAnchor = anchors[anchors.length - 1];
      let prevCardBox: CardObstacleBox | null = null;

      for (let i = 0; i < layerAnchors.length; i++) {
        const curr = layerAnchors[i];
        const remaining = layerAnchors.length - i;
        const maxAllowedHere = 0.89 - remaining * 0.044;
        const pHere = clampNum(Math.max(curr.rawP, prevP + 0.052), prevP + 0.045, maxAllowedHere);

        if (prevCardBox && curr.cardBox && Math.abs(prevAnchor.x - curr.x) > rootW * 0.35) {
          const corridorY = (prevCardBox.bottom + curr.cardBox.top) * 0.5;
          const midP = (prevP + pHere) * 0.5;
          anchors.push({
            p: midP,
            x: (prevAnchor.x + curr.x) * 0.5,
            y: corridorY,
            scale: cruiseScale,
            engine: 0.8,
            dock: 0,
            spineFrac: (prevAnchor.spineFrac + curr.spineFrac) * 0.5,
          });
        }

        prevP = pHere;
        computedLayerThresholds.push(Math.max(rawBridgeP + 0.015, pHere - 0.048));
        const layerAnchor: FlightAnchor = {
          p: pHere,
          x: curr.x,
          y: curr.y,
          scale: cruiseScale,
          engine: i === layerAnchors.length - 1 ? 0.64 : 0.82,
          dock: i === layerAnchors.length - 1 ? 0.08 : 0,
          spineFrac: curr.spineFrac,
        };
        anchors.push(layerAnchor);
        prevAnchor = layerAnchor;
        prevCardBox = curr.cardBox;
      }
    }

    const approachP = clampNum(Math.max(prevP + 0.038, 0.93), prevP + 0.025, 0.955);
    const dockThreshold = clampNum(approachP - 0.02, 0.885, 0.94);

    const lastCruiseAnchor = anchors[anchors.length - 1];
    anchors.push({
      p: approachP,
      x: dockCenterX + (lastCruiseAnchor.x - dockCenterX) * 0.35,
      y: dockCenterY - 20,
      scale: (cruiseScale + dockScale) * 0.5,
      engine: 0.38,
      dock: 0.62,
      spineFrac: Math.min(1, dockEndFrac * 0.96),
    });

    anchors.push({
      p: 1.0,
      x: dockCenterX,
      y: dockCenterY,
      scale: dockScale,
      engine: 0.2,
      dock: 1.0,
      spineFrac: Math.max(0.95, dockEndFrac),
    });

    const minX = Math.max(edgePadX + cruiseHalfW, 34);
    const maxX = Math.max(minX + 20, rootW - minX);
    const track = buildDenseFlightTrack(
      anchors,
      measuredWaypoints,
      computedLayerThresholds,
      dockThreshold,
      { x: dockCenterX, y: dockCenterY },
      { minX, maxX, cruiseHalfW, cruiseHalfH },
      obstacles,
      entryRampPath,
      entryRampStart,
      roadLockStartP
    );
    setFlightTrack(track);
  }, []);

  // Scroll-linked inertial progress: velocity-clamped critically damped smoothDamp avoids flick jerks
  const { scrollYProgress } = useScroll({ container: containerRef });
  const flightProgressMV = useMotionValue(0);
  const scrubProgress = prefersReducedMotion ? scrollYProgress : flightProgressMV;
  // Soft direction blend (1 = descending nose down, 0 = ascending nose up) with smooth aerospace banking (~0.45s)
  const scrollDirectionSpring = useSpring(1, {
    stiffness: 76,
    damping: 20,
    mass: 0.78,
  });

  const ensureFlightLoop = useCallback(() => {
    if (flightRafRef.current) return;
    let lastTs = performance.now();

    const step = (now: number) => {
      const rawDt = (now - lastTs) * 0.001;
      lastTs = now;
      const totalDt = clampNum(rawDt, 0.004, 0.25);

      const target = targetProgressRef.current;
      let curr = flightPosRef.current;
      let diff = target - curr;

      if (Math.abs(diff) < 0.00008 && Math.abs(flightVelRef.current) < 0.00015) {
        flightPosRef.current = target;
        flightVelRef.current = 0;
        flightProgressMV.set(target);
        flightRafRef.current = 0;
        return;
      }

      // Smooth time 0.28s & speed cap 0.92 progress/sec with 16ms sub-stepping keep wheel scrolling velvety
      const smoothTime = 0.28;
      const maxSpeed = 0.92;
      const omega = 2 / smoothTime;
      const maxChange = maxSpeed * smoothTime;
      const subSteps = Math.max(1, Math.ceil(totalDt / 0.016));
      const dt = totalDt / subSteps;

      for (let s = 0; s < subSteps; s++) {
        diff = target - curr;
        if (Math.abs(diff) < 0.00005 && Math.abs(flightVelRef.current) < 0.0001) {
          curr = target;
          flightVelRef.current = 0;
          break;
        }
        const x = omega * dt;
        const exp = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
        const clampedOffset = clampNum(-diff, -maxChange, maxChange);
        const effectiveTarget = curr - clampedOffset;

        const temp = (flightVelRef.current + omega * clampedOffset) * dt;
        flightVelRef.current = (flightVelRef.current - omega * temp) * exp;
        let nextPos = effectiveTarget + (clampedOffset + temp) * exp;

        if ((diff > 0) === (nextPos > target)) {
          nextPos = target;
          flightVelRef.current = 0;
        }
        curr = clampNum(nextPos, 0, 1);
      }

      flightPosRef.current = curr;
      flightProgressMV.set(curr);
      flightRafRef.current = requestAnimationFrame(step);
    };

    flightRafRef.current = requestAnimationFrame(step);
  }, [flightProgressMV]);

  const shipCenterX = useTransform(scrubProgress, flightTrack.stops, flightTrack.xs);
  const shipCenterY = useTransform(scrubProgress, flightTrack.stops, flightTrack.ys);
  const downRotateMV = useTransform(scrubProgress, flightTrack.stops, flightTrack.rotatesDown);
  const upRotateMV = useTransform(scrubProgress, flightTrack.stops, flightTrack.rotatesUp);
  const shipRotate = useTransform<number, number>(
    [downRotateMV, upRotateMV, scrollDirectionSpring],
    ([downDeg, upDeg, dirBlend]) => upDeg + dirBlend * (downDeg - upDeg)
  );
  const shipScale = useTransform(scrubProgress, flightTrack.stops, flightTrack.scales);
  const thrusterOpacity = useTransform(scrubProgress, flightTrack.stops, flightTrack.engines);
  const thrusterScale = useTransform(scrubProgress, flightTrack.stops, flightTrack.engines.map((e) => 0.45 + e * 0.48));
  const dockingBeamOpacity = useTransform(scrubProgress, flightTrack.stops, flightTrack.docks);
  const sparkOpacity = useTransform(scrubProgress, [0, 0.12, 0.82, 0.94, 1], [0.35, 0.55, 0.42, 0.05, 0]);
  const energizedSpineLength = useTransform(scrubProgress, flightTrack.stops, flightTrack.spineProgress);

  // Transform rig coordinates centered on actual pixel origin without layout properties or CSS variables
  const shipTransform = useMotionTemplate`translate3d(calc(${shipCenterX}px - 50%), calc(${shipCenterY}px - 50%), 0) rotate(${shipRotate}deg) scale(${shipScale})`;
  const thrusterTransform = useMotionTemplate`scale3d(${thrusterScale}, ${thrusterScale}, 1)`;

  // Track raw wheel scroll intent with directional hysteresis so small trackpad bounces never snap nose pitch
  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    const stepDelta = latest - prevScrollProgressRef.current;
    prevScrollProgressRef.current = latest;

    if ((stepDelta > 0 && scrollAccumRef.current < 0) || (stepDelta < 0 && scrollAccumRef.current > 0)) {
      scrollAccumRef.current = stepDelta;
    } else {
      scrollAccumRef.current += stepDelta;
    }

    if (latest <= 0.01) {
      scrollAccumRef.current = 0;
      scrollDirectionSpring.set(1);
    } else if (scrollAccumRef.current > 0.0045) {
      scrollDirectionSpring.set(1);
    } else if (scrollAccumRef.current < -0.0045) {
      scrollDirectionSpring.set(0);
    }

    targetProgressRef.current = latest;
    if (prefersReducedMotion) {
      flightPosRef.current = latest;
      flightVelRef.current = 0;
      flightProgressMV.set(latest);
    } else {
      ensureFlightLoop();
    }
  });

  // Keep discrete layer activation & terminal docking state synced symmetrically on scroll up and down
  useMotionValueEvent(scrubProgress, "change", (latest) => {
    let nextStage = -1;
    if (latest >= flightTrack.dockThreshold) {
      nextStage = 6;
    } else {
      for (let i = flightTrack.layerThresholds.length - 1; i >= 0; i--) {
        if (latest >= flightTrack.layerThresholds[i]) {
          nextStage = i;
          break;
        }
      }
    }

    if (nextStage !== activeStageRef.current) {
      activeStageRef.current = nextStage;
      setActiveStage(nextStage);
    }
  });

  // Initial scroll reset, ResizeObserver re-measurement, and scroll reveal observer
  useEffect(() => {
    const root = containerRef.current;
    if (!root) return;
    root.scrollTop = 0;

    const rafMeasure = requestAnimationFrame(() => {
      measureFlightTrack();
    });

    const ro =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(() => {
          requestAnimationFrame(measureFlightTrack);
        })
        : null;
    if (ro && contentRootRef.current) {
      ro.observe(contentRootRef.current);
    }
    window.addEventListener("resize", measureFlightTrack, { passive: true });

    const targets = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));
    const observer =
      targets.length > 0
        ? new IntersectionObserver(
          (entries) => {
            for (const entry of entries) {
              if (entry.isIntersecting) {
                (entry.target as HTMLElement).setAttribute("data-visible", "true");
              }
            }
          },
          { root, threshold: 0.14, rootMargin: "0px 0px -40px 0px" }
        )
        : null;

    if (observer) {
      for (const el of targets) {
        observer.observe(el);
      }
    }

    return () => {
      cancelAnimationFrame(rafMeasure);
      if (flightRafRef.current) {
        cancelAnimationFrame(flightRafRef.current);
        flightRafRef.current = 0;
      }
      ro?.disconnect();
      window.removeEventListener("resize", measureFlightTrack);
      observer?.disconnect();
    };
  }, [measureFlightTrack]);

  // Ambient cosmic starfield & drifting shard particles (Static camera, composite-light canvas)
  useEffect(() => {
    if (!canvasRef.current) return;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d", { alpha: true });
    if (!ctx) return;

    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let animId = 0;
    let width = window.innerWidth;
    let height = window.innerHeight;
    let dpr = Math.min(window.devicePixelRatio || 1, 1.5);

    const configureSize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    configureSize();
    window.addEventListener("resize", configureSize, { passive: true });

    const stars = Array.from({ length: 92 }, (_, idx) => ({
      x: Math.random(),
      y: Math.random(),
      size: Math.random() * 1.45 + 0.55,
      speed: 0.000009 + Math.random() * 0.000018,
      twinkle: Math.random() * Math.PI * 2,
      tint: isLight
        ? idx % 5 === 0
          ? "#6355E8"
          : idx % 3 === 0
            ? "#818CF8"
            : "#94A3B8"
        : idx % 5 === 0
          ? "#9A8CFF"
          : idx % 3 === 0
            ? "#C5BDFF"
            : "#E6EAF2",
    }));

    interface StreakParticle {
      active: boolean;
      x: number;
      y: number;
      vx: number;
      vy: number;
      len: number;
      alpha: number;
    }
    const streaks: StreakParticle[] = [
      { active: false, x: 0, y: 0, vx: -0.46, vy: 0.22, len: 88, alpha: 0 },
      { active: false, x: 0, y: 0, vx: -0.38, vy: 0.18, len: 68, alpha: 0 },
    ];
    let nextStreakIn = 900;

    let lastNow = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(48, Math.max(8, now - lastNow));
      lastNow = now;

      if (document.hidden) {
        animId = requestAnimationFrame(draw);
        return;
      }

      ctx.clearRect(0, 0, width, height);
      const twinkleStep = 0.0013 * dt;

      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.twinkle += twinkleStep;
        s.y -= s.speed * dt;
        if (s.y < -0.02) s.y = 1.02;

        const px = s.x * width;
        const py = s.y * height;
        const rawAlpha = 0.34 + Math.sin(s.twinkle) * 0.34;
        const clampedAlpha = isLight
          ? Math.max(0.1, Math.min(0.42, rawAlpha * 0.62))
          : rawAlpha < 0.14
            ? 0.14
            : rawAlpha > 0.78
              ? 0.78
              : rawAlpha;

        ctx.globalAlpha = clampedAlpha;
        ctx.fillStyle = s.tint;
        ctx.beginPath();
        ctx.arc(px, py, s.size, 0, Math.PI * 2);
        ctx.fill();
      }

      if (!prefersReduced) {
        nextStreakIn -= dt;
        if (nextStreakIn <= 0) {
          const slot = streaks.find((st) => !st.active);
          if (slot) {
            slot.active = true;
            slot.x = width * (0.45 + Math.random() * 0.55);
            slot.y = height * (0.04 + Math.random() * 0.35);
            slot.alpha = isLight ? 0.38 : 0.72;
          }
          nextStreakIn = 2600 + Math.random() * 2600;
        }

        for (let i = 0; i < streaks.length; i++) {
          const st = streaks[i];
          if (!st.active) continue;
          st.x += st.vx * dt;
          st.y += st.vy * dt;
          st.alpha -= 0.00055 * dt;
          if (st.alpha <= 0.02 || st.x < -120 || st.y > height + 80) {
            st.active = false;
            continue;
          }
          const tx = st.x - st.vx * (st.len / 0.45);
          const ty = st.y - st.vy * (st.len / 0.45);
          const grad = ctx.createLinearGradient(st.x, st.y, tx, ty);
          grad.addColorStop(0, isLight ? "#6355E8" : "#E6EAF2");
          grad.addColorStop(0.35, isLight ? "#818CF8" : "#9A8CFF");
          grad.addColorStop(1, isLight ? "rgba(99, 85, 232, 0)" : "rgba(154, 140, 255, 0)");
          ctx.globalAlpha = st.alpha;
          ctx.strokeStyle = grad;
          ctx.lineWidth = 1.4;
          ctx.beginPath();
          ctx.moveTo(st.x, st.y);
          ctx.lineTo(tx, ty);
          ctx.stroke();
        }
      }

      if (!prefersReduced) {
        animId = requestAnimationFrame(draw);
      }
    };

    animId = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", configureSize);
      if (scrollRafRef.current) {
        cancelAnimationFrame(scrollRafRef.current);
        scrollRafRef.current = 0;
      }
    };
  }, [isLight]);

  const handleScroll = () => {
    if (!containerRef.current || scrollRafRef.current) return;
    scrollRafRef.current = requestAnimationFrame(() => {
      scrollRafRef.current = 0;
      const el = containerRef.current;
      if (!el) return;
      const top = el.scrollTop;

      const isScrolled = top > 40;
      if (isScrolled !== headerScrolledRef.current) {
        headerScrolledRef.current = isScrolled;
        headerRef.current?.classList.toggle(styles.topNavbarScrolled, isScrolled);
      }

      // Apply GPU-only translate3d directly to dedicated parallax wrappers while Hero is near viewport
      const maxHeroScroll = window.innerHeight * 1.25;
      const clampedTop = top < maxHeroScroll ? top : maxHeroScroll;
      if (planetParallaxRef.current) {
        planetParallaxRef.current.style.transform = `translate3d(0, ${(clampedTop * 0.16).toFixed(1)}px, 0)`;
      }
      if (moonParallaxRef.current) {
        moonParallaxRef.current.style.transform = `translate3d(0, ${(clampedTop * 0.12).toFixed(1)}px, 0)`;
      }
      if (asteroidParallaxRef.current) {
        asteroidParallaxRef.current.style.transform = `translate3d(0, ${(clampedTop * 0.08).toFixed(1)}px, 0)`;
      }
    });
  };

  const scrollToRef = (ref: React.RefObject<HTMLElement | null>) => {
    ref.current?.scrollIntoView({ behavior: prefersReducedMotion ? "auto" : "smooth", block: "start" });
  };

  const milestoneCards = useMemo(() => {
    const isEn = locale === "en";
    const signalStrip = stocks
      .slice(0, 3)
      .map((s) => `${s.symbol} ${s.score}`)
      .join(" · ");

    if (isEn) {
      return [
        {
          num: "06",
          title: "Portfolio Risk 3D",
          slot: styles.roadmapSlotLeft,
          summary: "3D exposure torus & VaR 95% stress checks.",
        },
        {
          num: "05",
          title: "Citation-Locked AI",
          slot: styles.roadmapSlotCenterRight,
          summary: "Filing-backed answers with strict guardrails.",
        },
        {
          num: "04",
          title: "Top VN100 Signals",
          slot: styles.roadmapSlotLeft,
          summary: signalStrip || "CTG 88.5 · SIP 86.4 · FPT 84.1",
        },
        {
          num: "03",
          title: "Multi-Factor Alpha",
          slot: styles.roadmapSlotCenterLeft,
          summary: "Value, quality & 3D momentum regimes.",
        },
        {
          num: "02",
          title: "IAS 33 Normalizer",
          slot: styles.roadmapSlotRight,
          summary: "Split-adjusted continuous diluted EPS.",
        },
        {
          num: "01",
          title: "Point-in-Time Data",
          slot: styles.roadmapSlotLeft,
          summary: "HOSE · HNX · UPCOM bias-free history.",
        },
      ];
    }

    return [
      {
        num: "06",
        title: "Quản trị Danh mục 3D",
        slot: styles.roadmapSlotLeft,
        summary: "Phơi nhiễm 3D & kiểm định sốc VaR 95%.",
      },
      {
        num: "05",
        title: "AI Đối soát Bằng chứng",
        slot: styles.roadmapSlotCenterRight,
        summary: "Trích dẫn dữ liệu gốc, chống suy diễn.",
      },
      {
        num: "04",
        title: "Tín hiệu Top VN100",
        slot: styles.roadmapSlotLeft,
        summary: signalStrip || "CTG 88.5 · SIP 86.4 · FPT 84.1",
      },
      {
        num: "03",
        title: "Alpha Đa nhân tố",
        slot: styles.roadmapSlotCenterLeft,
        summary: "Định giá, chất lượng & xung lượng 3D.",
      },
      {
        num: "02",
        title: "Chuẩn hóa IAS 33",
        slot: styles.roadmapSlotRight,
        summary: "Điều chỉnh hồi tố cổ tức & EPS pha loãng.",
      },
      {
        num: "01",
        title: "Dữ liệu Chuẩn Thời gian",
        slot: styles.roadmapSlotLeft,
        summary: "HOSE · HNX · UPCOM không thiên lệch.",
      },
    ];
  }, [stocks, locale]);

  return (
    <div
      ref={containerRef}
      className={`${styles.gatewayOverlay} ${isBreaching ? styles.gatewayBreaching : ""}`}
      data-gateway-theme={effectiveTheme}
      onScroll={handleScroll}
      role="dialog"
      aria-modal="true"
      aria-label={t("Cổng dữ liệu InvestIntel", "InvestIntel Quantitative Gateway")}
    >
      {/* Subtle Ambient Telemetry Points */}
      <canvas ref={canvasRef} className={styles.starfieldCanvas} aria-hidden="true" />

      {/* Clean Top Fixed Workstation Navbar */}
      <header ref={headerRef} className={styles.topNavbar}>
        <button
          type="button"
          className={styles.brandBtn}
          onClick={() =>
            containerRef.current?.scrollTo({
              top: 0,
              behavior: prefersReducedMotion ? "auto" : "smooth",
            })
          }
          aria-label={t("Về đầu trang Gateway", "Scroll to Gateway top")}
        >
          <svg className={styles.brandMarkIcon} viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect x="2" y="2" width="28" height="28" rx="6" fill="var(--gw-surface)" stroke="var(--gw-border)" strokeWidth="1.2" />
            <path d="M9 21L14 15L18 18L23 11" stroke="var(--gw-ink)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="23" cy="11" r="2.2" fill="var(--gw-accent)" />
            <circle cx="9" cy="21" r="1.6" fill="var(--gw-ink-secondary)" />
          </svg>
          <span className={styles.brandWordmark}>InvestIntel</span>
        </button>

        <div className={styles.navRightActions}>
          <ThemeToggle variant="gateway" showSettingsLink={false} />
          <LanguageToggle variant="gateway" />
          <button
            type="button"
            className={styles.navDocsBtn}
            onClick={() => scrollToRef(roadmapSectionRef)}
          >
            {t("Quy trình", "Pipeline")}
          </button>
          <button
            type="button"
            className={styles.navConnectBtn}
            onClick={() => onBreach()}
          >
            {t("Truy cập", "Connect")}
          </button>
        </div>
      </header>

      <div ref={contentRootRef} className={styles.contentRoot}>
        {/* Scroll-Driven Continuous Spaceship Layer Across Hero -> 6-Layer Pipeline -> Terminal Dock */}
        <div className={styles.spaceshipFlightStage} aria-hidden="true">
          <motion.div
            ref={shipRigRef}
            className={`${styles.spaceshipFlightRig} ${prefersReducedMotion ? styles.spaceshipFlightRigReduced : ""
              }`}
            style={prefersReducedMotion ? undefined : { transform: shipTransform }}
            data-docked={activeStage === 6 ? "true" : "false"}
          >
            <div className={styles.spaceshipIdleBob}>
              <svg
                className={styles.spaceshipSvg}
                viewBox="-52 -24 430 284"
                fill="none"
                aria-hidden="true"
              >
                <defs>
                  <linearGradient id="hullMetal" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#354061" />
                    <stop offset="48%" stopColor="#191F2D" />
                    <stop offset="100%" stopColor="#101522" />
                  </linearGradient>
                  <linearGradient id="innerNozzle" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#101522" />
                    <stop offset="100%" stopColor="#9A8CFF" stopOpacity="0.95" />
                  </linearGradient>
                  <linearGradient id="plasmaOuter" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#9A8CFF" stopOpacity="0.92" />
                    <stop offset="48%" stopColor="#6D5CE6" stopOpacity="0.58" />
                    <stop offset="100%" stopColor="#191F2D" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="plasmaMid" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#E6EAF2" stopOpacity="0.96" />
                    <stop offset="46%" stopColor="#9A8CFF" stopOpacity="0.82" />
                    <stop offset="100%" stopColor="#6D5CE6" stopOpacity="0" />
                  </linearGradient>
                  <linearGradient id="plasmaCore" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#FFFFFF" stopOpacity="1" />
                    <stop offset="55%" stopColor="#C5BDFF" stopOpacity="0.9" />
                    <stop offset="100%" stopColor="#9A8CFF" stopOpacity="0" />
                  </linearGradient>
                  <radialGradient id="thrusterAura" cx="42%" cy="46%" r="56%">
                    <stop offset="0%" stopColor="#C5BDFF" stopOpacity="0.58" />
                    <stop offset="45%" stopColor="#9A8CFF" stopOpacity="0.28" />
                    <stop offset="100%" stopColor="#101522" stopOpacity="0" />
                  </radialGradient>
                  <linearGradient id="dockBeamGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stopColor="#9A8CFF" stopOpacity="0.85" />
                    <stop offset="100%" stopColor="#9A8CFF" stopOpacity="0" />
                  </linearGradient>
                </defs>

                {/* Scroll-Scrubbed Docking Tether Illuminating Toward Terminal Reticle at Final Approach */}
                <motion.g style={{ opacity: prefersReducedMotion ? 0 : dockingBeamOpacity }}>
                  <polygon points="154,158 196,174 176,246 130,230" fill="url(#dockBeamGrad)" opacity="0.28" />
                  <line x1="168" y1="164" x2="154" y2="238" stroke="#9A8CFF" strokeWidth="1.3" strokeDasharray="3 4" />
                  <circle cx="154" cy="240" r="3" fill="#C5BDFF" />
                </motion.g>

                {/* Engine Ion Exhaust Ambient Aura & Thrusters Modulated Smoothly by Scroll Phase */}
                <motion.g
                  style={{
                    opacity: prefersReducedMotion ? 0.55 : thrusterOpacity,
                    transform: prefersReducedMotion ? undefined : thrusterTransform,
                    transformOrigin: "260px 160px",
                  }}
                >
                  <circle cx="294" cy="184" r="76" fill="url(#thrusterAura)" className={styles.corePulse} />

                  {/* Dual Multi-Segment Supersonic Ion Plasma Plumes + 6 Shock Diamonds (Mach Disks) */}
                  <g className={styles.thrusterFlame}>
                    <polygon points="252,156 382,224 285,138" fill="#9A8CFF" opacity="0.2" />
                    <polygon points="256,154 374,218 282,140" fill="url(#plasmaOuter)" />
                    <polygon points="258,155 348,202 280,144" fill="url(#plasmaMid)" />
                    <polygon points="260,156 318,184 276,148" fill="url(#plasmaCore)" />

                    <polygon points="218,172 346,248 254,152" fill="#9A8CFF" opacity="0.2" />
                    <polygon points="222,170 338,242 252,154" fill="url(#plasmaOuter)" />
                    <polygon points="226,170 314,224 248,158" fill="url(#plasmaMid)" />
                    <polygon points="230,170 288,202 244,162" fill="url(#plasmaCore)" />

                    <g className={styles.shockDiamonds}>
                      <polygon points="274,157 283,155 289,163 280,165" fill="#FFFFFF" />
                      <polygon points="295,168 303,167 308,174 300,175" fill="#C5BDFF" opacity="0.92" />
                      <polygon points="315,179 322,178 326,184 319,185" fill="#9A8CFF" opacity="0.82" />
                      <polygon points="242,173 251,171 257,179 248,181" fill="#FFFFFF" />
                      <polygon points="264,186 272,185 277,192 269,193" fill="#C5BDFF" opacity="0.9" />
                      <polygon points="285,199 292,198 296,204 289,205" fill="#9A8CFF" opacity="0.78" />
                    </g>
                  </g>
                </motion.g>

                {/* Twin Sculpted Metallic Engine Nozzles + Glowing Core Throats */}
                <polygon points="242,146 276,140 270,162 238,164" fill="url(#hullMetal)" stroke="#9A8CFF" strokeWidth="0.9" />
                <ellipse cx="268" cy="152" rx="6" ry="8.5" transform="rotate(-18 268 152)" fill="url(#innerNozzle)" stroke="#E6EAF2" strokeWidth="1" />
                <polygon points="214,160 246,154 242,176 210,178" fill="url(#hullMetal)" stroke="#292F40" strokeWidth="0.9" />
                <ellipse cx="238" cy="167" rx="6" ry="8.5" transform="rotate(-18 238 167)" fill="url(#innerNozzle)" stroke="#E6EAF2" strokeWidth="1" />

                {/* Far Wing + Telemetry Conduit + Strobe */}
                <polygon points="92,74 268,118 244,144 134,108" fill="#1F2639" stroke="#292F40" strokeWidth="0.9" />
                <polygon points="154,92 268,118 244,132" fill="#2D3652" />
                <line x1="168" y1="98" x2="254" y2="122" stroke="#9A8CFF" strokeWidth="1.2" opacity="0.8" />
                <circle cx="270" cy="119" r="3" fill="#9A8CFF" className={styles.beaconBlink} />

                {/* Main Fuselage Matte Structural Facets */}
                <polygon points="24,46 168,104 148,128 84,96" fill="#D5DCEB" stroke="rgba(154,140,255,0.45)" strokeWidth="0.8" />
                <polygon points="24,46 84,96 112,126" fill="#8C98B8" />
                <polygon points="168,104 252,138 228,158 148,128" fill="#A6B1CC" />
                <polygon points="148,128 228,158 188,184 128,152" fill="#2A334D" />
                <line x1="48" y1="58" x2="152" y2="104" stroke="#292F40" strokeWidth="1.1" opacity="0.7" />
                <line x1="164" y1="114" x2="236" y2="144" stroke="#9A8CFF" strokeWidth="1.6" opacity="0.95" />
                <polygon points="74,78 96,86 90,94 68,84" fill="#101522" stroke="#292F40" strokeWidth="0.7" />

                {/* Lower Swept Wing + Energy Stripe + Wingtip Strobe */}
                <polygon points="118,128 198,164 176,198 112,158" fill="#1F273B" stroke="#292F40" strokeWidth="0.9" />
                <polygon points="118,128 176,198 152,202 104,152" fill="#141A28" />
                <polygon points="118,136 170,178 154,186 112,146" fill="#9A8CFF" opacity="0.78" />
                <line x1="126" y1="148" x2="170" y2="188" stroke="#E6EAF2" strokeWidth="1.2" opacity="0.85" />
                <circle cx="176" cy="198" r="3" fill="#E6EAF2" className={styles.beaconBlink} />

                {/* Optical Sensor Canopy */}
                <polygon points="108,82 172,108 158,124 122,110" fill="#191F2D" stroke="#9A8CFF" strokeWidth="1" />
                <polygon points="116,86 164,106 154,116 126,104" fill="#9A8CFF" opacity="0.72" />
                <polygon points="122,88 154,102 148,106 126,96" fill="#FFFFFF" opacity="0.9" />

                {/* Dorsal Fin Stabilizer */}
                <polygon points="190,118 244,104 236,138" fill="#94A0B8" stroke="rgba(230,234,242,0.45)" strokeWidth="0.8" />
                <polygon points="190,118 244,104 218,126" fill="#E6EAF2" />

                {/* Restrained Exhaust Sparks (attenuates to zero on final docking) */}
                <motion.g
                  style={{ opacity: prefersReducedMotion ? 0 : sparkOpacity }}
                  className={styles.sparkStream}
                >
                  <polygon points="334,148 346,142 342,154" fill="#9A8CFF" />
                  <polygon points="356,178 370,172 366,186" fill="#E6EAF2" />
                  <polygon points="326,218 340,212 336,224" fill="#C5BDFF" />
                </motion.g>
              </svg>
            </div>
          </motion.div>
        </div>

        {/* ================================================================
            SLIDE 1: MATTE DATA-WORKSTATION HERO (Kinetic Orbital Hardware & Ion Thrusters)
            ================================================================ */}
        <section ref={heroSectionRef} className={styles.heroSection}>
          {/* Top-Left Architectural Orbital Manifold */}
          <div ref={planetParallaxRef} className={styles.planetParallaxWrap} aria-hidden="true">
            <svg
              className={styles.planetTopLeft}
              viewBox="0 0 560 480"
              fill="none"
            >
              <defs>
                <radialGradient id="planetHalo" cx="55%" cy="48%" r="52%">
                  <stop offset="0%" stopColor={geo.accent} stopOpacity={isLight ? "0.14" : "0.22"} />
                  <stop offset="65%" stopColor={geo.ringFill} stopOpacity="0.08" />
                  <stop offset="100%" stopColor={geo.baseBg} stopOpacity="0" />
                </radialGradient>
                <clipPath id="planetSphereClip">
                  <circle cx="215" cy="185" r="154" />
                </clipPath>
              </defs>
              <circle cx="220" cy="188" r="220" fill="url(#planetHalo)" className={styles.corePulse} />
              {/* Rotating Outer Telemetry Reticle */}
              <circle
                cx="215"
                cy="185"
                r="186"
                stroke={geo.accentEdgeSoft}
                strokeWidth="1"
                strokeDasharray="10 18 3 12"
                className={styles.orbitalSpinSlow}
              />
              {/* Back Half of Orbital Axis Ring */}
              <g transform="rotate(14 215 190)">
                <path
                  d="M 18 192 C 122 146, 314 144, 444 188"
                  stroke={geo.stroke}
                  strokeWidth="1.4"
                  strokeDasharray="4 6"
                  fill="none"
                />
              </g>
              {/* Geodesic Matte Slate Manifold */}
              <g clipPath="url(#planetSphereClip)">
                <circle cx="215" cy="185" r="154" fill={geo.sphereBase} />
                <polygon points="105,35 190,25 162,92" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="190,25 282,42 224,98" fill={geo.facet2} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="190,25 224,98 162,92" fill={geo.facet3} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="282,42 355,106 278,128" fill={geo.facet4} stroke={geo.accentEdgeSoft} strokeWidth="0.8" />
                <polygon points="224,98 282,42 278,128" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="162,92 224,98 188,162" fill={geo.ringFill} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="224,98 278,128 248,186" fill={geo.facet2} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="188,162 224,98 248,186" fill={geo.facet3} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="278,128 355,106 368,194" fill={geo.facet5} stroke={geo.accentEdgeMid} strokeWidth="0.85" />
                <polygon points="248,186 278,128 368,194" fill={geo.facet3} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="248,186 368,194 316,278" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="188,162 248,186 226,254" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="226,254 248,186 316,278" fill={geo.facet3} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="62,98 105,35 162,92" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="62,98 162,92 122,165" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="122,165 162,92 188,162" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="62,98 122,165 55,205" fill={geo.facet7} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="55,205 122,165 138,248" fill={geo.facet8} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="122,165 188,162 174,242" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="174,242 188,162 226,254" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="138,248 174,242 226,254" fill={geo.facet7} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="138,248 226,254 198,332" fill={geo.facet7} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="226,254 316,278 242,338" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="198,332 226,254 242,338" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.7" />
                <polyline points="105,35 162,92 224,98 278,128 248,186 316,278" stroke={geo.accentEdgeMid} strokeWidth="1.1" fill="none" />
                <circle cx="278" cy="128" r="3" fill={geo.accent} className={styles.beaconBlink} />
              </g>
              <circle cx="215" cy="185" r="154" stroke={geo.strokeSubtle} strokeWidth="1.2" />
              {/* Front Technical Trajectory Arc + Orbiting Ring Shards */}
              <g transform="rotate(14 215 190)">
                <path
                  d="M 12 204 C 122 266, 308 268, 456 202 L 466 210 C 314 278, 118 276, 4 212 Z"
                  fill={geo.ringFill}
                  stroke={geo.strokeSubtle}
                  strokeWidth="0.9"
                  opacity="0.92"
                />
                <path
                  d="M 28 214 C 132 270, 306 272, 444 210"
                  stroke={geo.accent}
                  strokeWidth="1.4"
                  opacity="0.65"
                  fill="none"
                />
                <polygon points="118,242 152,250 144,262 108,254" fill={geo.ringArm} stroke={geo.stroke} strokeWidth="0.7" />
                <polygon points="264,254 312,244 320,256 274,266" fill={geo.ringArm} stroke={geo.accentEdgeMid} strokeWidth="0.7" />
                <circle cx="312" cy="249" r="3.4" fill={geo.beaconBright} className={styles.beaconBlink} />
              </g>
            </svg>
          </div>

          {/* Top-Right Pulsing Core Wireframe Node & Rotating Orbital Scanner */}
          <div ref={moonParallaxRef} className={styles.moonParallaxWrap} aria-hidden="true">
            <svg
              className={styles.moonTopRight}
              viewBox="0 0 500 430"
              fill="none"
            >
              <defs>
                <radialGradient id="cyanMoonCoreGlow" cx="46%" cy="54%" r="52%">
                  <stop offset="0%" stopColor={geo.accent} stopOpacity={isLight ? "0.28" : "0.45"} />
                  <stop offset="48%" stopColor={geo.accent} stopOpacity="0.14" />
                  <stop offset="100%" stopColor={geo.baseBg} stopOpacity="0" />
                </radialGradient>
              </defs>
              <circle cx="276" cy="192" r="160" fill="url(#cyanMoonCoreGlow)" className={styles.corePulse} />
              <circle cx="276" cy="192" r="108" fill={geo.sphereBase} stroke={geo.strokeSubtle} strokeWidth="1" />
              <circle
                cx="276"
                cy="192"
                r="134"
                stroke={geo.accentEdgeMid}
                strokeWidth="1"
                strokeDasharray="6 8 2 8"
                className={styles.orbitalSpinReverse}
              />
              <polygon points="196,120 282,84 260,164" fill={geo.facet3} stroke={geo.stroke} strokeWidth="0.8" />
              <polygon points="282,84 366,136 312,188" fill={geo.facet6} stroke={geo.stroke} strokeWidth="0.8" />
              <polygon points="366,136 382,222 312,188" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.8" />
              <polygon points="312,188 382,222 332,286" fill={geo.facet7} stroke={geo.stroke} strokeWidth="0.8" />
              <polygon points="172,186 248,162 214,232" fill={geo.facet1} stroke={geo.stroke} strokeWidth="0.8" />
              {/* Exposed Pulsing Core & Crystal Fissures */}
              <g className={styles.corePulse}>
                <polygon points="194,202 262,164 294,206 254,264 198,252" fill={geo.coreChamber} stroke={geo.accent} strokeWidth="1.1" />
                <polygon points="212,218 262,174 282,208 248,248" fill={geo.accent} opacity="0.55" />
                <polygon points="242,196 266,184 274,212 246,228" fill={geo.coreBright} opacity="0.92" />
                <polygon points="254,264 294,206 332,286 274,298" fill={geo.facet4} stroke={geo.accentEdgeMid} strokeWidth="0.8" />
                <polyline points="262,164 246,228 274,298" stroke={geo.coreBright} strokeWidth="1.2" opacity="0.72" fill="none" />
                <polyline points="194,202 246,228 312,188" stroke={geo.accent} strokeWidth="1.1" opacity="0.75" fill="none" />
              </g>
              {/* Orbiting Telemetry Satellites & Poly Shards */}
              <g className={styles.shardDriftSlow}>
                <polygon points="88,108 118,90 132,124 98,136" fill={geo.ringFill} stroke={geo.accentEdgeMid} strokeWidth="1" />
                <rect x="148" y="66" width="11" height="11" rx="2" fill={geo.ringFill} stroke={geo.strokeSubtle} strokeWidth="1" />
                <polygon points="74,264 106,248 118,284 82,292" fill={geo.ringFill} stroke={geo.strokeSubtle} strokeWidth="1" />
                <polygon points="362,68 394,54 406,86 372,96" fill={geo.facet2} stroke={geo.accentEdgeMid} strokeWidth="1" />
              </g>
              <g className={styles.shardDriftFast}>
                <polygon points="384,254 416,238 428,274 390,284" fill={geo.facet2} stroke={geo.accent} strokeWidth="0.9" />
                <circle cx="342" cy="318" r="4" fill={geo.accent} opacity="0.8" />
                <polygon points="154,206 172,196 178,220 158,224" fill={geo.beaconBright} opacity="0.85" />
              </g>
            </svg>
          </div>

          {/* Diagonal Wireframe Vector Mesh */}
          <div ref={asteroidParallaxRef} className={styles.asteroidParallaxWrap} aria-hidden="true">
            <svg
              className={styles.asteroidDiagonal}
              viewBox="0 0 1440 900"
              preserveAspectRatio="none"
              fill="none"
            >
              <line x1="60" y1="840" x2="1280" y2="210" stroke={geo.strokeSubtle} strokeWidth="1" strokeDasharray="6 8" opacity="0.6" />
              <g className={styles.asteroidFloat1}>
                <polygon points="94,744 148,704 198,732 162,796 106,784" fill={geo.facet6} stroke={geo.strokeSubtle} strokeWidth="1" />
                <polygon points="94,744 148,704 156,748 106,784" fill={geo.ringFill} />
                <polygon points="148,704 198,732 156,748" fill={geo.facet3} stroke={geo.accentEdgeMid} strokeWidth="0.8" />
                <polygon points="134,740 156,728 160,746 138,754" fill={geo.accent} opacity="0.65" className={styles.beaconBlink} />

                <polygon points="218,684 268,656 302,684 276,728 228,718" fill={geo.facet7} stroke={geo.strokeSubtle} strokeWidth="0.9" />
                <polygon points="218,684 268,656 262,696" fill={geo.ringFill} />
              </g>

              <g className={styles.asteroidFloat2}>
                <polygon points="338,634 390,606 424,638 386,678 346,664" fill={geo.facet7} stroke={geo.strokeSubtle} strokeWidth="0.9" />
                <polygon points="338,634 390,606 384,644" fill={geo.ringFill} />
                <polyline points="338,634 384,644 386,678" stroke={geo.accentEdgeMid} strokeWidth="1" fill="none" />

                <polygon points="498,582 546,554 578,582 546,618 508,608" fill={geo.facet6} stroke={geo.strokeSubtle} strokeWidth="0.9" />
                <circle cx="546" cy="582" r="3" fill={geo.accent} opacity="0.7" className={styles.beaconBlink} />
              </g>

              <g className={styles.asteroidFloat1}>
                <polygon points="932,374 982,348 1014,380 976,412 940,398" fill={geo.facet6} stroke={geo.strokeSubtle} strokeWidth="0.9" />
                <polygon points="932,374 982,348 972,384" fill={geo.ringFill} />
                <circle cx="972" cy="384" r="2.8" fill={geo.beaconBright} opacity="0.75" className={styles.beaconBlink} />

                <polygon points="1084,296 1134,272 1168,302 1130,334 1094,320" fill={geo.facet7} stroke={geo.strokeSubtle} strokeWidth="0.9" />
              </g>
            </svg>
          </div>

          {/* Hero Copy & CTA Row */}
          <div ref={heroPanelRef} className={styles.heroCenterContent}>
            <span className={styles.eyebrowCaption}>
              {t("ĐỊNH LƯỢNG · VN100", "QUANT · VN100")}
            </span>
            <h1 className={styles.heroTitle}>InvestIntel</h1>
            <p className={styles.heroSubtitle}>
              {t(
                "Phân tích định lượng & AI đối soát dữ liệu gốc.",
                "Quantitative equity & evidence-cited AI."
              )}
            </p>
            <div className={styles.ctaRow}>
              <button
                type="button"
                className={styles.primaryActionBtn}
                onClick={() => scrollToRef(roadmapSectionRef)}
              >
                {t("Khám phá quy trình", "Explore Pipeline")}
              </button>
              <button
                type="button"
                className={styles.secondaryActionBtn}
                onClick={() => onBreach()}
              >
                {t("Mở trạm phân tích", "Launch Terminal")}
              </button>
            </div>
          </div>

          <button
            type="button"
            className={styles.scrollDownPrompt}
            onClick={() => scrollToRef(roadmapSectionRef)}
          >
            <span className={styles.scrollDownText}>
              {t("CUỘN ĐỂ KHÁM PHÁ", "SCROLL TO EXPLORE")}
            </span>
            <span className={styles.heroSpineBridge} aria-hidden="true">
              <span className={styles.heroSpineDot} />
              <span className={styles.heroSpinePulse} />
            </span>
          </button>
        </section>

        {/* ================================================================
            SLIDE 2: ARCHITECTURAL PIPELINE FLOW & WORKSTATION PORTAL
            ================================================================ */}
        <section ref={roadmapSectionRef} id="gateway-roadmap" className={styles.valleySection}>
          <svg
            className={styles.valleyBgSvg}
            viewBox="0 0 1440 1600"
            preserveAspectRatio="none"
            fill="none"
            aria-hidden="true"
          >
            <defs>
              <path
                id="pipelineSpinePath"
                d={PIPELINE_PATH_D}
              />
              <radialGradient id="packetHalo" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor={geo.coreBright} stopOpacity="0.95" />
                <stop offset="40%" stopColor={geo.accent} stopOpacity="0.72" />
                <stop offset="100%" stopColor={geo.accent} stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Architectural Winding Data Pipeline Conduit */}
            <path
              d={PIPELINE_PATH_D}
              stroke="var(--gw-road-outer)"
              className={styles.pipelineRailOuter}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d={PIPELINE_PATH_D}
              stroke="var(--gw-road-bed)"
              className={styles.pipelineBedInner}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {flightTrack.entryRampPath ? (
              <g aria-hidden="true">
                <path
                  d={flightTrack.entryRampPath}
                  stroke="var(--gw-accent)"
                  fill="none"
                  className={styles.pipelineOnRamp}
                  vectorEffect="non-scaling-stroke"
                  strokeLinecap="round"
                />
                {flightTrack.entryRampStart ? (
                  <circle
                    cx={flightTrack.entryRampStart.x}
                    cy={flightTrack.entryRampStart.y}
                    r="3.2"
                    fill="var(--gw-node-fill)"
                    stroke="var(--gw-accent)"
                    strokeWidth="1.2"
                    className={styles.pipelineOnRampNode}
                    vectorEffect="non-scaling-stroke"
                  />
                ) : null}
              </g>
            ) : null}
            <path
              ref={pipelinePathRef}
              d={PIPELINE_PATH_D}
              stroke="var(--gw-road-trace)"
              className={styles.pipelineTraceBase}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Scrubbed Energized Trace Advancing With Spacecraft Along Conduit */}
            <motion.path
              d={PIPELINE_PATH_D}
              stroke="var(--gw-accent)"
              className={styles.pipelineActiveTrace}
              style={{ pathLength: energizedSpineLength }}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d={PIPELINE_PATH_D}
              stroke="var(--gw-accent)"
              className={`${styles.pipelineTraceDash} ${styles.pipelineCurrentStream}`}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Flowing Data Telemetry Packets Riding Along Curved Conduit */}
            <g className={styles.pipelinePackets}>
              <g>
                <circle r="14" fill="url(#packetHalo)" />
                <circle r="4" fill={geo.beaconBright} />
                <animateMotion dur="8.5s" repeatCount="indefinite" begin="0s">
                  <mpath href="#pipelineSpinePath" />
                </animateMotion>
              </g>
              <g>
                <circle r="12" fill="url(#packetHalo)" />
                <circle r="3.4" fill={geo.accent} />
                <animateMotion dur="8.5s" repeatCount="indefinite" begin="2.8s">
                  <mpath href="#pipelineSpinePath" />
                </animateMotion>
              </g>
              <g>
                <circle r="12" fill="url(#packetHalo)" />
                <circle r="3.4" fill={geo.accentLight} />
                <animateMotion dur="8.5s" repeatCount="indefinite" begin="5.6s">
                  <mpath href="#pipelineSpinePath" />
                </animateMotion>
              </g>
            </g>

            {/* 6 Scroll-Synchronized Layer Nodes Along Pipeline Conduit */}
            <g>
              <circle cx="720" cy="40" r="8" fill="var(--gw-node-fill)" stroke="var(--gw-border)" strokeWidth="1.2" />
              <circle
                cx="720"
                cy="40"
                r="2.8"
                fill={activeStage >= 0 ? "var(--gw-accent)" : "var(--gw-ink-muted)"}
              />

              {flightTrack.waypoints.map((wp, idx) => {
                const state =
                  idx === activeStage ? "active" : activeStage > idx ? "visited" : "pending";
                const isLit = state !== "pending";
                const isActive = state === "active";
                return (
                  <g key={wp.num} className={styles.pipelineWaypointGroup} data-layer-state={state}>
                    {isActive && !prefersReducedMotion && (
                      <circle
                        cx={wp.x}
                        cy={wp.y}
                        r="22"
                        fill="none"
                        stroke={geo.accentEdgeStrong}
                        strokeWidth="1.2"
                        className={styles.waypointPulse}
                      />
                    )}
                    <circle
                      cx={wp.x}
                      cy={wp.y}
                      r={isActive ? 12 : 9.5}
                      fill="var(--gw-node-fill)"
                      stroke={isActive ? "var(--gw-accent)" : isLit ? geo.accentEdgeMid : "var(--gw-border)"}
                      strokeWidth={isActive ? "1.6" : "1.2"}
                    />
                    <circle
                      cx={wp.x}
                      cy={wp.y}
                      r={isActive ? 4.5 : 3.2}
                      fill={isActive ? "var(--gw-ink)" : isLit ? "var(--gw-accent)" : "var(--gw-ink-muted)"}
                    />
                  </g>
                );
              })}

              {activeStage === 6 && !prefersReducedMotion && (
                <circle
                  cx="720"
                  cy="1350"
                  r="20"
                  fill="none"
                  stroke={geo.accentEdgeStrong}
                  strokeWidth="1.1"
                  className={styles.waypointPulseAlt}
                />
              )}
              <circle
                cx="720"
                cy="1350"
                r="9"
                fill="var(--gw-node-fill)"
                stroke={activeStage === 6 ? "var(--gw-accent)" : "var(--gw-border)"}
                strokeWidth="1.2"
              />
              <circle
                cx="720"
                cy="1350"
                r="3.4"
                fill={activeStage === 6 ? "var(--gw-ink)" : "var(--gw-ink-muted)"}
              />
            </g>
          </svg>

          {/* Section Header (Pipeline Overview) */}
          <div ref={valleyHeaderRef} className={`${styles.valleyHeader} ${styles.revealBlock}`} data-reveal>
            <span className={styles.eyebrowCaption}>{t("QUY TRÌNH 6 TẦNG", "6-LAYER PIPELINE")}</span>
            <h2 className={styles.sectionTitle}>
              {t("Từ Dữ liệu đến Quyết định", "From Data to Decision")}
            </h2>
            <p className={styles.valleyHeaderBody}>
              {t(
                "6 tầng xử lý đồng bộ theo thời gian thực.",
                "Six synchronized layers from raw ticks to conviction."
              )}
            </p>
          </div>

          {/* Staggered Pipeline Layer Cards 06..01 */}
          <div className={styles.roadmapFlow}>
            {milestoneCards.map((card, idx) => {
              const meta = getMilestoneMeta(card.num, locale);
              const layerNumber = Number(card.num);
              const layerState =
                idx === activeStage ? "active" : activeStage > idx ? "visited" : "pending";
              return (
                <div
                  key={card.num}
                  ref={(el) => {
                    cardSlotRefs.current[idx] = el;
                  }}
                  className={`${styles.roadmapSlot} ${card.slot} ${styles.revealBlock}`}
                  data-reveal
                  data-layer-state={layerState}
                  style={{ "--reveal-delay": `${idx * 70}ms` } as React.CSSProperties}
                >
                  <div className={styles.milestoneStage}>
                    <article className={styles.milestoneCard}>
                      <div className={styles.milestoneLayerRow}>
                        <span className={styles.milestoneLayerTag}>{meta.layer}</span>
                        <span className={styles.milestoneMetric}>{meta.metric}</span>
                      </div>
                      <div className={styles.milestoneHeader}>
                        <span className={styles.milestoneNumber}>{card.num}</span>
                        <h3 className={styles.milestoneTitle}>{card.title}</h3>
                      </div>
                      <p className={styles.milestoneSummary}>{card.summary}</p>
                      <div className={styles.milestoneFooter}>
                        <span className={styles.milestoneProgress} aria-hidden="true">
                          <span
                            className={styles.milestoneProgressFill}
                            style={{ "--progress-scale": `${layerNumber / 6}` } as React.CSSProperties}
                          />
                        </span>
                        <span className={styles.milestoneStageLabel}>
                          {t(`TẦNG ${layerNumber}/6`, `LAYER ${layerNumber}/6`)}
                        </span>
                      </div>
                    </article>
                    <div className={styles.milestoneStem} aria-hidden="true">
                      <span className={styles.milestoneStemHalo} />
                      <span
                        ref={(el) => {
                          stemNodeRefs.current[idx] = el;
                        }}
                        className={styles.milestoneStemNode}
                      />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Matte Workstation Connect Panel at Pipeline Terminus with Counter-Rotating Telemetry Reticle */}
          <div
            ref={portalRef}
            className={`${styles.roadEndPortal} ${styles.revealBlock}`}
            data-reveal
            data-docked={activeStage === 6 ? "true" : "false"}
          >
            <div ref={reticleRef} className={styles.portalReticle} aria-hidden="true">
              <span className={styles.portalRingOuter} />
              <span className={styles.portalRingInner} />
              <span className={styles.portalGem} />
            </div>
            <span className={styles.eyebrowCaption}>
              {t("SẴN SÀNG TRUY CẬP", "READY TO ENTER")}
            </span>
            <h2 className={styles.portalHeading}>
              {t("Khởi chạy Trạm Phân tích", "Initialize Workstation")}
            </h2>
            <p className={styles.portalSubtext}>
              {t(
                "Dữ liệu VN100, mô hình định giá và AI kiểm chứng đã sẵn sàng.",
                "VN100 engine, benchmarks & cited AI online."
              )}
            </p>
            <ul className={styles.portalStatusList}>
              <li className={styles.portalStatusItem}>
                <span className={styles.portalStatusDot} aria-hidden="true" />
                <span className={styles.portalStatusLabel}>{t("DỮ LIỆU EOD", "EOD DATA")}</span>
                <span className={styles.portalStatusValue}>HOSE · HNX · UPCOM</span>
              </li>
              <li className={styles.portalStatusItem}>
                <span className={styles.portalStatusDot} aria-hidden="true" />
                <span className={styles.portalStatusLabel}>{t("ĐỊNH GIÁ", "VALUATION")}</span>
                <span className={styles.portalStatusValue}>DCF · RIM · IAS 33</span>
              </li>
              <li className={styles.portalStatusItem}>
                <span className={styles.portalStatusDot} aria-hidden="true" />
                <span className={styles.portalStatusLabel}>{t("TRỢ LÝ AI", "AI ANALYST")}</span>
                <span className={styles.portalStatusValue}>{t("BẰNG CHỨNG GỐC", "EVIDENCE-CITED")}</span>
              </li>
            </ul>
            <div className={styles.ctaRow}>
              <button
                type="button"
                className={styles.primaryActionBtn}
                onClick={() => onBreach()}
              >
                {t("Kết nối Trạm Phân tích →", "Connect Workstation →")}
              </button>
              <button
                type="button"
                className={styles.secondaryActionBtn}
                onClick={() => onBreach("/ai")}
              >
                {t("Mở Trợ lý AI", "Open AI Analyst")}
              </button>
            </div>
            <span className={styles.portalFootHint}>
              {t("NHẤN KẾT NỐI HOẶC ESC", "CONNECT OR PRESS ESC")}
            </span>
          </div>
        </section>
      </div>
    </div>
  );
}

export default TacticalGateway;
