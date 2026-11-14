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
import { getOpportunityScanner, type OpportunityFilters } from "@/lib/api";
import { useLocale, type AppLocale } from "@/lib/i18n";
import LanguageToggle from "@/components/language-toggle";
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
    "06": { vi: ["TẦNG QUYẾT ĐỊNH", "VaR 95%"], en: ["DECISION LAYER", "VaR 95%"] },
    "05": { vi: ["TẦNG KIỂM CHỨNG", "14 CÔNG CỤ"], en: ["VERIFICATION LAYER", "14 TOOLS"] },
    "04": { vi: ["TẦNG TÍN HIỆU", "TOP 3 VN100"], en: ["SIGNAL LAYER", "TOP 3 VN100"] },
    "03": { vi: ["TẦNG MÔ HÌNH", "7 NHÂN TỐ"], en: ["MODEL LAYER", "7 FACTORS"] },
    "02": { vi: ["TẦNG CHUẨN HÓA", "EPS PHA LOÃNG"], en: ["NORMALIZATION LAYER", "DILUTED EPS"] },
    "01": { vi: ["TẦNG DỮ LIỆU", "3 SÀN"], en: ["DATA LAYER", "3 EXCHANGES"] },
  };
  const entry = meta[num];
  if (!entry) return { layer: "", metric: "" };
  const [layer, metric] = isEn ? entry.en : entry.vi;
  return { layer, metric };
}

export function TacticalGateway({
  topStocks,
}: TacticalGatewayProps): JSX.Element | null {
  const router = useRouter();
  const { locale, t } = useLocale();
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false
  );
  const [isGatewayOpen, setIsGatewayOpen] = useState(false);
  const [isBreaching, setIsBreaching] = useState(false);
  const [fetchedStocks, setFetchedStocks] = useState<TacticalGatewayStock[]>(DEFAULT_TOP_STOCKS);
  const stocks = useMemo(
    () => (topStocks && topStocks.length > 0 ? topStocks : fetchedStocks),
    [topStocks, fetchedStocks]
  );

  const containerRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const planetParallaxRef = useRef<HTMLDivElement>(null);
  const moonParallaxRef = useRef<HTMLDivElement>(null);
  const asteroidParallaxRef = useRef<HTMLDivElement>(null);
  const roadmapSectionRef = useRef<HTMLElement>(null);
  const scrollRafRef = useRef<number>(0);
  const headerScrolledRef = useRef<boolean>(false);

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
      .catch(() => {});
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
      headerScrolledRef.current = false;
      requestAnimationFrame(() => {
        if (containerRef.current) {
          containerRef.current.scrollTop = 0;
        }
        headerRef.current?.classList.remove(styles.topNavbarScrolled);
        if (planetParallaxRef.current) planetParallaxRef.current.style.transform = "translate3d(0, 0, 0)";
        if (moonParallaxRef.current) moonParallaxRef.current.style.transform = "translate3d(0, 0, 0)";
        if (asteroidParallaxRef.current) asteroidParallaxRef.current.style.transform = "translate3d(0, 0, 0)";
      });
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

  // IntersectionObserver for smooth scroll-driven slide/card reveals across all 3 slides
  useEffect(() => {
    if (!isGatewayOpen || !containerRef.current) return;
    const root = containerRef.current;
    const targets = Array.from(root.querySelectorAll<HTMLElement>("[data-reveal]"));
    if (targets.length === 0) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).setAttribute("data-visible", "true");
          }
        }
      },
      { root, threshold: 0.14, rootMargin: "0px 0px -40px 0px" }
    );

    for (const el of targets) {
      observer.observe(el);
    }
    return () => observer.disconnect();
  }, [isGatewayOpen]);

  // Ambient cosmic starfield & drifting shard particles (Static camera, composite-light canvas)
  useEffect(() => {
    if (!isGatewayOpen || !canvasRef.current) return;
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

    const stars = Array.from({ length: 56 }, (_, idx) => ({
      x: Math.random(),
      y: Math.random(),
      size: Math.random() * 1.0 + 0.55,
      speed: 0.000006 + Math.random() * 0.000014,
      twinkle: Math.random() * Math.PI * 2,
      tint: idx % 6 === 0 ? "#9A8CFF" : "#E6EAF2",
    }));

    let lastNow = performance.now();

    const draw = (now: number) => {
      const dt = Math.min(48, Math.max(8, now - lastNow));
      lastNow = now;

      if (document.hidden) {
        animId = requestAnimationFrame(draw);
        return;
      }

      ctx.clearRect(0, 0, width, height);
      const twinkleStep = 0.0009 * dt;

      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.twinkle += twinkleStep;
        s.y -= s.speed * dt;
        if (s.y < -0.02) s.y = 1.02;

        const px = s.x * width;
        const py = s.y * height;
        const alpha = 0.16 + Math.sin(s.twinkle) * 0.12;

        ctx.globalAlpha = alpha < 0.06 ? 0.06 : alpha > 0.34 ? 0.34 : alpha;
        ctx.fillStyle = s.tint;
        ctx.beginPath();
        ctx.arc(px, py, s.size, 0, Math.PI * 2);
        ctx.fill();
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
  }, [isGatewayOpen]);

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
    ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const milestoneCards = useMemo(() => {
    const isEn = locale === "en";
    const topSignals = stocks.slice(0, 3).map(
      (s) =>
        isEn
          ? `${s.symbol} · Score ${s.score}/100 (${s.upside ?? "+20%"})`
          : `${s.symbol} · Điểm ${s.score}/100 (${s.upside ?? "+20%"})`
    );
    const defaultSignals = isEn
      ? ["CTG · Score 88/100 (+18.2%)", "SIP · Score 86/100 (+36.9%)", "FPT · Score 84/100 (+22.5%)"]
      : ["CTG · Điểm 88/100 (+18.2%)", "SIP · Điểm 86/100 (+36.9%)", "FPT · Điểm 84/100 (+22.5%)"];

    if (isEn) {
      return [
        {
          num: "06",
          title: "Portfolio Risk 3D",
          slot: styles.roadmapSlotCenterLeft,
          bullets: [
            "3D torus exposure telemetry",
            "VaR 95% & Sharpe benchmark",
            "Rate-shock stress testing",
          ],
        },
        {
          num: "05",
          title: "Citation-Locked AI",
          slot: styles.roadmapSlotCenterRight,
          bullets: [
            "Evidence-first analysis streaming",
            "Financial line-item filing audit",
            "Zero-hallucination guardrails",
          ],
        },
        {
          num: "04",
          title: "Top VN100 Signals",
          slot: styles.roadmapSlotLeft,
          bullets: topSignals.length > 0 ? topSignals : defaultSignals,
        },
        {
          num: "03",
          title: "Multi-Factor Alpha",
          slot: styles.roadmapSlotCenterLeft,
          bullets: [
            "Value, quality & leverage scoring",
            "Momentum regime detection",
            "Interactive 3D factor manifold",
          ],
        },
        {
          num: "02",
          title: "IAS 33 Normalizer",
          slot: styles.roadmapSlotRight,
          bullets: [
            "Bonus & rights issue adjustment",
            "Diluted EPS series continuity",
            "Apples-to-apples valuation multiples",
          ],
        },
        {
          num: "01",
          title: "Point-in-Time Data",
          slot: styles.roadmapSlotLeft,
          bullets: [
            "HOSE / HNX / UPCOM EOD sync",
            "Survivorship-bias free history",
            "Audit-ready PostgreSQL store",
          ],
        },
      ];
    }

    return [
      {
        num: "06",
        title: "Quản trị Rủi ro 3D",
        slot: styles.roadmapSlotCenterLeft,
        bullets: [
          "Trực quan hóa phơi nhiễm tài sản 3D",
          "Đo lường VaR 95% & tỷ số Sharpe",
          "Kiểm định kịch bản sốc lãi suất",
        ],
      },
      {
        num: "05",
        title: "AI Đối soát Bằng chứng",
        slot: styles.roadmapSlotCenterRight,
        bullets: [
          "Phản hồi ưu tiên trích dẫn dữ liệu gốc",
          "Đối chiếu từng khoản mục BCTC",
          "Cơ chế kiểm duyệt chống suy diễn ảo",
        ],
      },
      {
        num: "04",
        title: "Tín hiệu Top VN100",
        slot: styles.roadmapSlotLeft,
        bullets: topSignals.length > 0 ? topSignals : defaultSignals,
      },
      {
        num: "03",
        title: "Alpha Đa nhân tố",
        slot: styles.roadmapSlotCenterLeft,
        bullets: [
          "Chấm điểm định giá & chất lượng nền tảng",
          "Nhận diện trạng thái xung lượng dòng tiền",
          "Khối lập phương nhân tố 3D tương tác",
        ],
      },
      {
        num: "02",
        title: "Chuẩn hóa theo IAS 33",
        slot: styles.roadmapSlotRight,
        bullets: [
          "Điều chỉnh hồi tố cổ tức & phát hành thêm",
          "Bảo toàn chuỗi EPS pha loãng liên tục",
          "So sánh bội số định giá đồng nhất",
        ],
      },
      {
        num: "01",
        title: "Dữ liệu Chuẩn Mốc Thời gian",
        slot: styles.roadmapSlotLeft,
        bullets: [
          "Đồng bộ giá EOD sàn HOSE / HNX / UPCOM",
          "Loại bỏ hoàn toàn thiên lệch sống sót",
          "Kho dữ liệu kiểm toán SQL & PostgreSQL",
        ],
      },
    ];
  }, [stocks, locale]);

  if (!mounted || !isGatewayOpen) {
    return null;
  }

  return createPortal(
    <div
      ref={containerRef}
      className={`${styles.gatewayOverlay} ${isBreaching ? styles.gatewayBreaching : ""}`}
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
          onClick={() => containerRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label={t("Về đầu trang Gateway", "Scroll to Gateway top")}
        >
          <svg className={styles.brandMarkIcon} viewBox="0 0 32 32" fill="none" aria-hidden="true">
            <rect x="2" y="2" width="28" height="28" rx="6" fill="#191F2D" stroke="#292F40" strokeWidth="1.2" />
            <path d="M9 21L14 15L18 18L23 11" stroke="#E6EAF2" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            <circle cx="23" cy="11" r="2.2" fill="#9A8CFF" />
            <circle cx="9" cy="21" r="1.6" fill="#94A0B8" />
          </svg>
          <span className={styles.brandWordmark}>InvestIntel</span>
        </button>

        <div className={styles.navRightActions}>
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
            onClick={() => triggerBreach()}
          >
            {t("Truy cập", "Connect")}
          </button>
        </div>
      </header>

      <div className={styles.contentRoot}>
        {/* ================================================================
            SLIDE 1: MATTE DATA-WORKSTATION HERO (Restrained Geometric Architecture)
            ================================================================ */}
        <section className={styles.heroSection}>
          {/* Top-Left Architectural Orbital Manifold */}
          <div ref={planetParallaxRef} className={styles.planetParallaxWrap} aria-hidden="true">
            <svg
              className={styles.planetTopLeft}
              viewBox="0 0 560 480"
              fill="none"
            >
            <defs>
              <radialGradient id="planetHalo" cx="55%" cy="48%" r="52%">
                <stop offset="0%" stopColor="#9A8CFF" stopOpacity="0.14" />
                <stop offset="65%" stopColor="#191F2D" stopOpacity="0.06" />
                <stop offset="100%" stopColor="#101522" stopOpacity="0" />
              </radialGradient>
              <clipPath id="planetSphereClip">
                <circle cx="215" cy="185" r="154" />
              </clipPath>
            </defs>
            <circle cx="220" cy="188" r="220" fill="url(#planetHalo)" />
            {/* Back Half of Orbital Axis Ring */}
            <g transform="rotate(14 215 190)">
              <path
                d="M 18 192 C 122 146, 314 144, 444 188"
                stroke="#292F40"
                strokeWidth="1.4"
                strokeDasharray="4 6"
                fill="none"
              />
            </g>
            {/* Geodesic Matte Slate Manifold */}
            <g clipPath="url(#planetSphereClip)">
              <circle cx="215" cy="185" r="154" fill="#131928" />
              <polygon points="105,35 190,25 162,92" fill="#1A2133" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="190,25 282,42 224,98" fill="#1F273B" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="190,25 224,98 162,92" fill="#1D2437" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="282,42 355,106 278,128" fill="#232B42" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="224,98 282,42 278,128" fill="#1C2336" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="162,92 224,98 188,162" fill="#191F2D" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="224,98 278,128 248,186" fill="#20283E" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="188,162 224,98 248,186" fill="#181F2F" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="278,128 355,106 368,194" fill="#232B42" stroke="rgba(154,140,255,0.22)" strokeWidth="0.8" />
              <polygon points="248,186 278,128 368,194" fill="#1E2538" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="248,186 368,194 316,278" fill="#1A2033" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="188,162 248,186 226,254" fill="#161C2B" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="226,254 248,186 316,278" fill="#181F2F" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="62,98 105,35 162,92" fill="#151B2A" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="62,98 162,92 122,165" fill="#171E2E" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="122,165 162,92 188,162" fill="#141A28" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="62,98 122,165 55,205" fill="#131926" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="55,205 122,165 138,248" fill="#111623" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="122,165 188,162 174,242" fill="#151B2A" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="174,242 188,162 226,254" fill="#171E2E" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="138,248 174,242 226,254" fill="#131926" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="138,248 226,254 198,332" fill="#121825" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="226,254 316,278 242,338" fill="#171D2D" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="198,332 226,254 242,338" fill="#141A28" stroke="#292F40" strokeWidth="0.7" />
              <polyline points="105,35 162,92 224,98 278,128 248,186 316,278" stroke="rgba(154,140,255,0.34)" strokeWidth="1" fill="none" />
              <circle cx="278" cy="128" r="2.8" fill="#9A8CFF" />
            </g>
            <circle cx="215" cy="185" r="154" stroke="#292F40" strokeWidth="1.2" />
            {/* Front Technical Trajectory Arc */}
            <g transform="rotate(14 215 190)">
              <path
                d="M 12 204 C 122 266, 308 268, 456 202 L 466 210 C 314 278, 118 276, 4 212 Z"
                fill="#191F2D"
                stroke="#292F40"
                strokeWidth="0.9"
                opacity="0.9"
              />
              <path
                d="M 28 214 C 132 270, 306 272, 444 210"
                stroke="#9A8CFF"
                strokeWidth="1.2"
                opacity="0.48"
                fill="none"
              />
              <circle cx="312" cy="249" r="3" fill="#9A8CFF" />
            </g>
            </svg>
          </div>

          {/* Top-Right Restraint Wireframe Node */}
          <div ref={moonParallaxRef} className={styles.moonParallaxWrap} aria-hidden="true">
            <svg
              className={styles.moonTopRight}
              viewBox="0 0 500 430"
              fill="none"
            >
            <defs>
              <radialGradient id="cyanMoonCoreGlow" cx="46%" cy="54%" r="50%">
                <stop offset="0%" stopColor="#9A8CFF" stopOpacity="0.14" />
                <stop offset="65%" stopColor="#191F2D" stopOpacity="0.06" />
                <stop offset="100%" stopColor="#101522" stopOpacity="0" />
              </radialGradient>
            </defs>
            <circle cx="276" cy="192" r="155" fill="url(#cyanMoonCoreGlow)" />
            <circle cx="276" cy="192" r="108" fill="#131928" stroke="#292F40" strokeWidth="1" />
            <circle cx="276" cy="192" r="132" stroke="#292F40" strokeWidth="0.9" strokeDasharray="3 5" />
            <polygon points="196,120 282,84 260,164" fill="#181F2F" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="282,84 366,136 312,188" fill="#151B2A" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="366,136 382,222 312,188" fill="#1A2133" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="312,188 382,222 332,286" fill="#131926" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="172,186 248,162 214,232" fill="#171E2E" stroke="#292F40" strokeWidth="0.8" />
            <g>
              <polygon points="194,202 262,164 294,206 254,264 198,252" fill="#1D2438" stroke="rgba(154,140,255,0.4)" strokeWidth="1" />
              <polygon points="212,218 262,174 282,208 248,248" fill="#222B42" stroke="#292F40" strokeWidth="0.7" />
              <polygon points="254,264 294,206 332,286 274,298" fill="#181F2F" stroke="#292F40" strokeWidth="0.7" />
              <polyline points="262,164 246,228 274,298" stroke="#9A8CFF" strokeWidth="1.1" opacity="0.55" fill="none" />
              <circle cx="246" cy="228" r="3" fill="#9A8CFF" />
            </g>
            {/* Subtle Telemetry Satellites */}
            <g className={styles.shardDriftSlow}>
              <rect x="96" y="102" width="12" height="12" rx="2" fill="#191F2D" stroke="#292F40" strokeWidth="1" />
              <rect x="148" y="66" width="10" height="10" rx="2" fill="#191F2D" stroke="#292F40" strokeWidth="1" />
              <circle cx="88" cy="272" r="4" fill="#191F2D" stroke="rgba(154,140,255,0.45)" strokeWidth="1" />
              <rect x="372" y="64" width="12" height="12" rx="2" fill="#191F2D" stroke="#292F40" strokeWidth="1" />
            </g>
            <g className={styles.shardDriftFast}>
              <circle cx="402" cy="256" r="4.5" fill="#191F2D" stroke="#292F40" strokeWidth="1" />
              <circle cx="342" cy="318" r="3.5" fill="#9A8CFF" opacity="0.55" />
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
            <line x1="60" y1="840" x2="1280" y2="210" stroke="#292F40" strokeWidth="1" strokeDasharray="6 8" opacity="0.55" />
            <g className={styles.asteroidFloat1}>
              <polygon points="94,744 148,704 198,732 162,796 106,784" fill="#151B29" stroke="#292F40" strokeWidth="1" />
              <polygon points="94,744 148,704 156,748 106,784" fill="#191F2D" />
              <polygon points="148,704 198,732 156,748" fill="#1E2536" stroke="#292F40" strokeWidth="0.8" />
              <circle cx="156" cy="748" r="2.8" fill="#9A8CFF" opacity="0.65" />

              <polygon points="218,684 268,656 302,684 276,728 228,718" fill="#141A28" stroke="#292F40" strokeWidth="0.9" />
              <polygon points="218,684 268,656 262,696" fill="#191F2D" />
            </g>

            <g className={styles.asteroidFloat2}>
              <polygon points="338,634 390,606 424,638 386,678 346,664" fill="#141A28" stroke="#292F40" strokeWidth="0.9" />
              <polygon points="338,634 390,606 384,644" fill="#191F2D" />
              <polyline points="338,634 384,644 386,678" stroke="rgba(154,140,255,0.28)" strokeWidth="0.9" fill="none" />

              <polygon points="498,582 546,554 578,582 546,618 508,608" fill="#151B29" stroke="#292F40" strokeWidth="0.9" />
              <circle cx="546" cy="582" r="2.5" fill="#9A8CFF" opacity="0.55" />
            </g>

            <g className={styles.asteroidFloat1}>
              <polygon points="932,374 982,348 1014,380 976,412 940,398" fill="#151B29" stroke="#292F40" strokeWidth="0.9" />
              <polygon points="932,374 982,348 972,384" fill="#191F2D" />
              <circle cx="972" cy="384" r="2.5" fill="#9A8CFF" opacity="0.6" />

              <polygon points="1084,296 1134,272 1168,302 1130,334 1094,320" fill="#141A28" stroke="#292F40" strokeWidth="0.9" />
            </g>
            </svg>
          </div>

          {/* Bottom-Right Restraint Geometric Telemetry Craft */}
          <svg
            className={styles.spaceshipBottomRight}
            viewBox="0 0 400 265"
            fill="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="hullMetal" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#262E45" />
                <stop offset="55%" stopColor="#191F2D" />
                <stop offset="100%" stopColor="#121826" />
              </linearGradient>
              <linearGradient id="vectorTrail" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#9A8CFF" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#9A8CFF" stopOpacity="0" />
              </linearGradient>
            </defs>

            {/* Clean Restraint Vector Trajectory Lines */}
            <g className={styles.thrusterFlame}>
              <line x1="268" y1="154" x2="386" y2="216" stroke="url(#vectorTrail)" strokeWidth="2" strokeDasharray="5 5" />
              <line x1="238" y1="168" x2="352" y2="236" stroke="url(#vectorTrail)" strokeWidth="2" strokeDasharray="5 5" />
              <circle cx="294" cy="168" r="2" fill="#9A8CFF" opacity="0.65" />
              <circle cx="264" cy="184" r="2" fill="#9A8CFF" opacity="0.5" />
            </g>

            {/* Matte Engine Housing */}
            <polygon points="242,146 276,140 270,162 238,164" fill="url(#hullMetal)" stroke="#292F40" strokeWidth="1" />
            <ellipse cx="268" cy="152" rx="5.5" ry="8" transform="rotate(-18 268 152)" fill="#101522" stroke="#9A8CFF" strokeWidth="1" />
            <polygon points="214,160 246,154 242,176 210,178" fill="url(#hullMetal)" stroke="#292F40" strokeWidth="1" />
            <ellipse cx="238" cy="167" rx="5.5" ry="8" transform="rotate(-18 238 167)" fill="#101522" stroke="#9A8CFF" strokeWidth="1" />

            {/* Far Wing */}
            <polygon points="92,74 268,118 244,144 134,108" fill="#1F2639" stroke="#292F40" strokeWidth="0.9" />
            <polygon points="154,92 268,118 244,132" fill="#2A334B" />
            <circle cx="270" cy="119" r="2.6" fill="#9A8CFF" />

            {/* Main Fuselage Matte Structural Facets */}
            <polygon points="24,46 168,104 148,128 84,96" fill="#2A334D" stroke="#36415E" strokeWidth="0.9" />
            <polygon points="24,46 84,96 112,126" fill="#1F273B" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="168,104 252,138 228,158 148,128" fill="#252D43" stroke="#292F40" strokeWidth="0.8" />
            <polygon points="148,128 228,158 188,184 128,152" fill="#181F2F" stroke="#292F40" strokeWidth="0.8" />
            <line x1="164" y1="114" x2="236" y2="144" stroke="#9A8CFF" strokeWidth="1.2" opacity="0.7" />
            <polygon points="74,78 96,86 90,94 68,84" fill="#101522" stroke="#292F40" strokeWidth="0.7" />

            {/* Lower Swept Wing */}
            <polygon points="118,128 198,164 176,198 112,158" fill="#1C2336" stroke="#292F40" strokeWidth="0.9" />
            <polygon points="118,128 176,198 152,202 104,152" fill="#141A28" />
            <line x1="126" y1="148" x2="170" y2="188" stroke="#9A8CFF" strokeWidth="1" opacity="0.6" />
            <circle cx="176" cy="198" r="2.6" fill="#9A8CFF" />

            {/* Optical Sensor Canopy */}
            <polygon points="108,82 172,108 158,124 122,110" fill="#151B2A" stroke="#9A8CFF" strokeWidth="0.9" />
            <polygon points="116,86 164,106 154,116 126,104" fill="#262F48" />
            <line x1="122" y1="88" x2="152" y2="101" stroke="#E6EAF2" strokeWidth="0.9" opacity="0.6" />

            {/* Dorsal Fin */}
            <polygon points="190,118 244,104 236,138" fill="#222A40" stroke="#292F40" strokeWidth="0.9" />
          </svg>

          {/* Hero Copy & CTA Row */}
          <div className={styles.heroCenterContent}>
            <span className={styles.eyebrowCaption}>
              {t("TRẠM PHÂN TÍCH ĐỊNH LƯỢNG · VN100", "QUANTITATIVE EQUITY WORKSTATION · VN100")}
            </span>
            <h1 className={styles.heroTitle}>InvestIntel</h1>
            <p className={styles.heroSubtitle}>
              {t(
                "Hệ sinh thái Nghiên cứu Cổ phiếu Định lượng & Trợ lý AI Kiểm chứng Dữ liệu.",
                "Institutional Quantitative Equity & Evidence-Backed AI Research Ecosystem."
              )}
              <br />
              {t("Khai phá. Định giá. Kiểm chứng. Đầu tư.", "Discover. Value. Verify. Invest.")}
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
                onClick={() => triggerBreach()}
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
            <span>
              {t(
                "CUỘN XUỐNG ĐỂ THEO DÕI QUY TRÌNH DỮ LIỆU 6 TẦNG",
                "SCROLL DOWN TO TRACE THE 6-LAYER DATA PIPELINE"
              )}
            </span>
            <span className={styles.heroSpineBridge} aria-hidden="true">
              <span className={styles.heroSpineDot} />
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
            {/* Architectural Winding Data Pipeline Conduit */}
            <path
              d="M 720 0 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1500"
              stroke="#292F40"
              className={styles.pipelineRailOuter}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 720 0 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1500"
              stroke="#151B29"
              className={styles.pipelineBedInner}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 720 0 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1500"
              stroke="#292F40"
              className={styles.pipelineTraceBase}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 720 0 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1500"
              stroke="#9A8CFF"
              strokeOpacity="0.45"
              className={styles.pipelineTraceDash}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* Precision Waypoint Coordinates Along Pipeline Axis */}
            <g>
              <circle cx="720" cy="40" r="8" fill="#101522" stroke="#292F40" strokeWidth="1.2" />
              <circle cx="720" cy="40" r="2.8" fill="#9A8CFF" />

              <circle cx="640" cy="320" r="10" fill="#101522" stroke="#292F40" strokeWidth="1.2" />
              <circle cx="640" cy="320" r="3.4" fill="#9A8CFF" />

              <circle cx="955" cy="675" r="10" fill="#101522" stroke="#292F40" strokeWidth="1.2" />
              <circle cx="955" cy="675" r="3.4" fill="#9A8CFF" />

              <circle cx="375" cy="1065" r="10" fill="#101522" stroke="#292F40" strokeWidth="1.2" />
              <circle cx="375" cy="1065" r="3.4" fill="#9A8CFF" />

              <circle cx="720" cy="1485" r="9" fill="#101522" stroke="#292F40" strokeWidth="1.2" />
              <circle cx="720" cy="1485" r="3.2" fill="#9A8CFF" />
            </g>
          </svg>

          {/* Section Header (Pipeline Overview) */}
          <div className={`${styles.valleyHeader} ${styles.revealBlock}`} data-reveal>
            <span className={styles.eyebrowCaption}>{t("QUY TRÌNH 6 TẦNG", "6-LAYER PIPELINE")}</span>
            <h2 className={styles.sectionTitle}>
              {t("Từ Dữ liệu Thô đến Quyết định", "From Raw Data to Decision")}
            </h2>
            <p className={styles.valleyHeaderBody}>
              {t(
                "Dòng dữ liệu chảy qua 6 tầng xử lý: từ giá EOD chuẩn mốc thời gian, chuẩn hóa IAS 33, mô hình đa nhân tố, tín hiệu VN100, AI đối soát bằng chứng cho đến đo lường rủi ro danh mục.",
                "Data flows through six processing layers: Point-in-Time EOD prices, IAS 33 normalization, multi-factor models, VN100 signals, evidence-audited AI, and portfolio risk measurement."
              )}
            </p>
          </div>

          {/* Staggered Pipeline Layer Cards 06..01 */}
          <div className={styles.roadmapFlow}>
            {milestoneCards.map((card, idx) => {
              const meta = getMilestoneMeta(card.num, locale);
              const layerNumber = Number(card.num);
              return (
                <div
                  key={card.num}
                  className={`${styles.roadmapSlot} ${card.slot} ${styles.revealBlock}`}
                  data-reveal
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
                      <ul className={styles.milestoneList}>
                        {card.bullets.map((bullet, bIdx) => (
                          <li key={bIdx} className={styles.milestoneItem}>
                            <span className={styles.milestoneArrow} aria-hidden="true">
                              →
                            </span>
                            <span>{bullet}</span>
                          </li>
                        ))}
                      </ul>
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
                      <span className={styles.milestoneStemNode} />
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Matte Workstation Connect Panel at Pipeline Terminus */}
          <div className={`${styles.roadEndPortal} ${styles.revealBlock}`} data-reveal>
            <div className={styles.portalBadge} aria-hidden="true">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <rect x="2" y="2" width="14" height="14" rx="3" stroke="#292F40" strokeWidth="1.2" />
                <path d="M5.5 11.5L8 9L5.5 6.5" stroke="#9A8CFF" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                <line x1="9.5" y1="11.5" x2="12.5" y2="11.5" stroke="#E6EAF2" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </div>
            <span className={styles.eyebrowCaption}>
              {t("HOÀN TẤT QUY TRÌNH · SẴN SÀNG TRUY CẬP", "END OF PIPELINE · READY TO ENTER")}
            </span>
            <h2 className={styles.portalHeading}>
              {t("Khởi chạy Trạm Phân tích", "Initialize Workstation")}
            </h2>
            <p className={styles.portalSubtext}>
              {t(
                "Toàn bộ dữ liệu định lượng VN100, biểu đồ đối sánh theo mốc thời gian và trợ lý AI đối soát bằng chứng gốc đã sẵn sàng kết nối.",
                "Full VN100 quantitative datasets, Point-in-Time valuation benchmarks, and evidence-cited AI analysis are ready to connect."
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
                <span className={styles.portalStatusLabel}>{t("MÔ HÌNH ĐỊNH GIÁ", "VALUATION MODELS")}</span>
                <span className={styles.portalStatusValue}>DCF · RIM · IAS 33</span>
              </li>
              <li className={styles.portalStatusItem}>
                <span className={styles.portalStatusDot} aria-hidden="true" />
                <span className={styles.portalStatusLabel}>{t("TRỢ LÝ AI", "AI ANALYST")}</span>
                <span className={styles.portalStatusValue}>{t("TRÍCH DẪN BẰNG CHỨNG", "EVIDENCE-CITED")}</span>
              </li>
            </ul>
            <div className={styles.ctaRow}>
              <button
                type="button"
                className={styles.primaryActionBtn}
                onClick={() => triggerBreach()}
              >
                {t("Kết nối Trạm Phân tích →", "Connect Workstation →")}
              </button>
              <button
                type="button"
                className={styles.secondaryActionBtn}
                onClick={() => triggerBreach("/ai")}
              >
                {t("Mở Trợ lý AI", "Open AI Analyst")}
              </button>
            </div>
            <span className={styles.portalFootHint}>
              {t(
                "NHẤN KẾT NỐI HOẶC PHÍM ESC ĐỂ BƯỚC VÀO BẢNG ĐIỀU KHIỂN",
                "CLICK CONNECT OR PRESS ESC TO ENTER THE DASHBOARD"
              )}
            </span>
          </div>
        </section>
      </div>
    </div>,
    document.body
  );
}

export default TacticalGateway;
