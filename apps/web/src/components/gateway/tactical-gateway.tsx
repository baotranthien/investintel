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

interface ProductShowcase {
  id: string;
  index: string;
  shortLabel: string;
  eyebrow: string;
  title: string;
  ctaLabel: string;
  route: string;
  desc: string;
  specs: string[];
}

function getProductShowcases(locale: AppLocale): ProductShowcase[] {
  if (locale === "en") {
    return [
      {
        id: "quant",
        index: "01",
        shortLabel: "QUANT",
        eyebrow: "OUR PRODUCTS",
        title: "QUANT ENGINE",
        ctaLabel: "QUANT ENGINE",
        route: "/screener",
        desc: "InvestIntel Quant Engine normalizes Point-in-Time EOD market data across HOSE, HNX, and UPCOM while isolating deterministic valuation models (DCF, RIM, IAS 33 normalized P/E) before synthesizing VN100 opportunity scores.",
        specs: ["DCF · RIM · IAS 33 P/E", "100 VN100 equities · 3 exchanges", "0–100 opportunity score"],
      },
      {
        id: "ai",
        index: "02",
        shortLabel: "AI",
        eyebrow: "OUR PRODUCTS",
        title: "AI ANALYST",
        ctaLabel: "AI ANALYST",
        route: "/ai",
        desc: "Hybrid RAG financial statement co-pilot with verifiable source citations. Every thesis covering earnings growth, margin trajectory, and leverage risk is strictly anchored to audited line items with zero-hallucination checks.",
        specs: ["Hybrid RAG + source citations", "14 analysis tools", "Line-item filing audit"],
      },
      {
        id: "screener",
        index: "03",
        shortLabel: "3D",
        eyebrow: "OUR PRODUCTS",
        title: "3D SCREENER",
        ctaLabel: "3D SCREENER",
        route: "/screener",
        desc: "Interactive real-time 3D multi-factor manifold visualizing Value, Quality, Momentum, and Low-Volatility dispersion across Vietnam equities to surface undervalued opportunities with deep margins of safety.",
        specs: ["7 quantitative factors", "Interactive 3D factor cube", "Margin-of-safety filters"],
      },
      {
        id: "portfolio",
        index: "04",
        shortLabel: "RISK",
        eyebrow: "OUR PRODUCTS",
        title: "RISK TERMINAL",
        ctaLabel: "RISK TERMINAL",
        route: "/portfolio",
        desc: "Simulates portfolio weights and computes parametric Value-at-Risk (VaR 95%), Sharpe Ratio, Maximum Drawdown, and automated macro stress tests under interest-rate and FX shock scenarios.",
        specs: ["VaR 95% · Sharpe ratio", "Maximum drawdown", "Rate & FX shock scenarios"],
      },
    ];
  }

  return [
    {
      id: "quant",
      index: "01",
      shortLabel: "ĐỊNH LƯỢNG",
      eyebrow: "PHÂN HỆ CỐT LÕI",
      title: "ĐỘNG CƠ ĐỊNH LƯỢNG",
      ctaLabel: "MỞ ĐỘNG CƠ ĐỊNH LƯỢNG",
      route: "/screener",
      desc: "Chuẩn hóa dữ liệu giá cuối ngày theo đúng mốc thời gian trên toàn sàn HOSE, HNX và UPCOM; tách bạch hoàn toàn các mô hình định giá định lượng (DCF, RIM, P/E điều chỉnh theo chuẩn IAS 33) trước khi tổng hợp điểm cơ hội VN100.",
      specs: ["DCF · RIM · P/E IAS 33", "100 mã VN100 · 3 sàn", "Điểm cơ hội 0–100"],
    },
    {
      id: "ai",
      index: "02",
      shortLabel: "TRỢ LÝ AI",
      eyebrow: "PHÂN HỆ CỐT LÕI",
      title: "TRỢ LÝ PHÂN TÍCH AI",
      ctaLabel: "MỞ TRỢ LÝ AI",
      route: "/ai",
      desc: "Trợ lý đối soát báo cáo tài chính ứng dụng truy xuất đa tầng (Hybrid RAG) và trích dẫn bằng chứng gốc. Mọi luận điểm về tăng trưởng, biên lợi nhuận và rủi ro đòn bẩy đều neo chặt vào dòng số liệu thực tế, loại bỏ suy diễn ảo.",
      specs: ["Hybrid RAG + trích dẫn gốc", "14 công cụ phân tích", "Đối soát từng khoản mục BCTC"],
    },
    {
      id: "screener",
      index: "03",
      shortLabel: "BỘ LỌC 3D",
      eyebrow: "PHÂN HỆ CỐT LÕI",
      title: "BỘ LỌC ĐA NHÂN TỐ 3D",
      ctaLabel: "MỞ BỘ LỌC 3D",
      route: "/screener",
      desc: "Không gian trực quan hóa đa nhân tố Giá trị — Chất lượng — Xung lượng — Biến động thấp trong mô hình 3D thời gian thực, hỗ trợ sàng lọc nhanh cổ phiếu có biên an toàn vượt trội.",
      specs: ["7 nhân tố định lượng", "Khối lập phương 3D tương tác", "Lọc theo biên an toàn"],
    },
    {
      id: "portfolio",
      index: "04",
      shortLabel: "RỦI RO",
      eyebrow: "PHÂN HỆ CỐT LÕI",
      title: "QUẢN TRỊ RỦI RO DANH MỤC",
      ctaLabel: "MỞ QUẢN TRỊ RỦI RO",
      route: "/portfolio",
      desc: "Mô phỏng tỷ trọng phân bổ danh mục, tính toán Giá trị chịu rủi ro (VaR 95%), tỷ số Sharpe, mức sụt giảm tối đa và kiểm định sức chịu đựng trước kịch bản biến động lãi suất và tỷ giá.",
      specs: ["VaR 95% · Tỷ số Sharpe", "Mức sụt giảm tối đa (MDD)", "Kịch bản sốc lãi suất & tỷ giá"],
    },
  ];
}

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

function getWhyStats(locale: AppLocale) {
  if (locale === "en") {
    return [
      { value: "100", label: "VN100 EQUITIES NORMALIZED" },
      { value: "3", label: "HOSE · HNX · UPCOM" },
      { value: "7", label: "QUANT FACTORS" },
      { value: "14", label: "AI ANALYSIS TOOLS" },
    ];
  }
  return [
    { value: "100", label: "MÃ VN100 CHUẨN HÓA" },
    { value: "3", label: "SÀN HOSE · HNX · UPCOM" },
    { value: "7", label: "NHÂN TỐ ĐỊNH LƯỢNG" },
    { value: "14", label: "CÔNG CỤ PHÂN TÍCH AI" },
  ];
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
  const [productIndex, setProductIndex] = useState(0);
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
  const whySectionRef = useRef<HTMLElement>(null);
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

    const stars = Array.from({ length: 88 }, (_, idx) => ({
      x: Math.random(),
      y: Math.random(),
      size: Math.random() * 1.9 + 0.65,
      speed: 0.00001 + Math.random() * 0.000022,
      twinkle: Math.random() * Math.PI * 2,
      tint: idx % 5 === 0 ? "#A5F3FC" : idx % 7 === 0 ? "#F9A8D4" : "#FFFFFF",
      isShard: idx % 13 === 0,
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
      const twinkleStep = 0.0014 * dt;

      for (let i = 0; i < stars.length; i++) {
        const s = stars[i];
        s.twinkle += twinkleStep;
        s.y -= s.speed * dt;
        if (s.y < -0.02) s.y = 1.02;

        const px = s.x * width;
        const py = s.y * height;
        const alpha = 0.36 + Math.sin(s.twinkle) * 0.38;

        ctx.globalAlpha = alpha < 0.14 ? 0.14 : alpha > 0.92 ? 0.92 : alpha;
        ctx.fillStyle = s.tint;

        if (s.isShard) {
          ctx.save();
          ctx.translate(px, py);
          ctx.rotate(s.twinkle * 0.3);
          ctx.beginPath();
          ctx.moveTo(0, -5);
          ctx.lineTo(4.2, 4);
          ctx.lineTo(-4.2, 4);
          ctx.closePath();
          ctx.fill();
          ctx.restore();
        } else {
          ctx.beginPath();
          ctx.arc(px, py, s.size, 0, Math.PI * 2);
          ctx.fill();
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

  const productShowcases = useMemo(() => getProductShowcases(locale), [locale]);
  const whyStats = useMemo(() => getWhyStats(locale), [locale]);
  const activeProduct = productShowcases[productIndex] ?? productShowcases[0];

  const milestoneCards = useMemo(() => {
    const isEn = locale === "en";
    const topSignals = stocks.slice(0, 3).map(
      (s) =>
        isEn
          ? `${s.symbol} · SCORE ${s.score}/100 (${s.upside ?? "+20%"})`
          : `${s.symbol} · ĐIỂM ${s.score}/100 (${s.upside ?? "+20%"})`
    );
    const defaultSignals = isEn
      ? ["CTG · SCORE 88/100 (+18.2%)", "SIP · SCORE 86/100 (+36.9%)", "FPT · SCORE 84/100 (+22.5%)"]
      : ["CTG · ĐIỂM 88/100 (+18.2%)", "SIP · ĐIỂM 86/100 (+36.9%)", "FPT · ĐIỂM 84/100 (+22.5%)"];

    if (isEn) {
      return [
        {
          num: "06",
          title: "PORTFOLIO RISK 3D",
          slot: styles.roadmapSlotCenterLeft,
          bullets: [
            "TORUS 3D EXPOSURE TELEMETRY",
            "VAR 95% & SHARPE BENCHMARK",
            "RATE-SHOCK STRESS TESTING",
          ],
        },
        {
          num: "05",
          title: "CITATION-LOCKED AI",
          slot: styles.roadmapSlotCenterRight,
          bullets: [
            "EVIDENCE-FIRST STREAMING",
            "FINANCIAL LINE-ITEM AUDIT",
            "ZERO-HALLUCINATION GUARD",
          ],
        },
        {
          num: "04",
          title: "TOP VN100 SIGNALS",
          slot: styles.roadmapSlotLeft,
          bullets: topSignals.length > 0 ? topSignals : defaultSignals,
        },
        {
          num: "03",
          title: "MULTI-FACTOR ALPHA",
          slot: styles.roadmapSlotCenterLeft,
          bullets: [
            "VALUE & QUALITY SCORING",
            "MOMENTUM REGIME DETECTION",
            "INTERACTIVE 3D FACTOR CUBE",
          ],
        },
        {
          num: "02",
          title: "IAS 33 NORMALIZER",
          slot: styles.roadmapSlotRight,
          bullets: [
            "BONUS & RIGHTS ADJUSTMENT",
            "DILUTED EPS CONTINUITY",
            "APPLES-TO-APPLES MULTIPLES",
          ],
        },
        {
          num: "01",
          title: "POINT-IN-TIME DATA",
          slot: styles.roadmapSlotLeft,
          bullets: [
            "HOSE / HNX / UPCOM EOD SYNC",
            "SURVIVORSHIP-BIAS FREE",
            "AUDIT-READY SQL & POSTGRES",
          ],
        },
      ];
    }

    return [
      {
        num: "06",
        title: "RỦI RO DANH MỤC 3D",
        slot: styles.roadmapSlotCenterLeft,
        bullets: [
          "Trực quan hóa phơi nhiễm tài sản 3D",
          "Đo lường VaR 95% & tỷ số Sharpe",
          "Kiểm định kịch bản sốc lãi suất",
        ],
      },
      {
        num: "05",
        title: "AI ĐỐI SOÁT BẰNG CHỨNG",
        slot: styles.roadmapSlotCenterRight,
        bullets: [
          "PHẢN HỒI ĐẶT BẰNG CHỨNG LÊN HÀNG ĐẦU",
          "ĐỐI CHIẾU TỪNG KHOẢN MỤC BCTC GỐC",
          "CƠ CHẾ KIỂM DUYỆT CHỐNG SUY DIỄN ẢO",
        ],
      },
      {
        num: "04",
        title: "TÍN HIỆU TOP VN100",
        slot: styles.roadmapSlotLeft,
        bullets: topSignals.length > 0 ? topSignals : defaultSignals,
      },
      {
        num: "03",
        title: "ALPHA ĐA NHÂN TỐ",
        slot: styles.roadmapSlotCenterLeft,
        bullets: [
          "CHẤM ĐIỂM ĐỊNH GIÁ & CHẤT LƯỢNG NỀN TẢNG",
          "NHẬN DIỆN TRẠNG THÁI XUNG LƯỢNG DÒNG TIỀN",
          "KHỐI LẬP PHƯƠNG NHÂN TỐ 3D TƯƠNG TÁC",
        ],
      },
      {
        num: "02",
        title: "CHUẨN HÓA THEO IAS 33",
        slot: styles.roadmapSlotRight,
        bullets: [
          "ĐIỀU CHỈNH HỒI TỐ CỔ TỨC & PHÁT HÀNH THÊM",
          "BẢO TOÀN CHUỖI EPS PHA LOÃNG LIÊN TỤC",
          "SO SÁNH BỘI SỐ ĐỊNH GIÁ ĐỒNG NHẤT",
        ],
      },
      {
        num: "01",
        title: "DỮ LIỆU CHUẨN MỐC THỜI GIAN",
        slot: styles.roadmapSlotLeft,
        bullets: [
          "ĐỒNG BỘ GIÁ EOD SÀN HOSE / HNX / UPCOM",
          "LOẠI BỎ HOÀN TOÀN THIÊN LỆCH SỐNG SÓT",
          "KHO DỮ LIỆU KIỂM TOÁN SQL & POSTGRES",
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
      aria-label={t("Cổng trải nghiệm InvestIntel 3D", "InvestIntel Scrollytelling Gateway")}
    >
      {/* Twinkling Starfield & Cosmic Shards */}
      <canvas ref={canvasRef} className={styles.starfieldCanvas} aria-hidden="true" />

      {/* Clean Top Fixed Navbar (Brand Left, EN/VI + PIPELINE + CONNECT Right) */}
      <header ref={headerRef} className={styles.topNavbar}>
        <button
          type="button"
          className={styles.brandBtn}
          onClick={() => containerRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label={t("Về đầu trang Gateway", "Scroll to Gateway top")}
        >
          <svg className={styles.brandSpinIcon} viewBox="0 0 40 40" fill="none" aria-hidden="true">
            <polygon points="20,2 34,14 20,24 6,14" fill="#FFFFFF" />
            <polygon points="20,24 34,14 20,38 6,14" fill="#A5F3FC" opacity="0.88" />
            <ellipse cx="20" cy="18" rx="17" ry="6" stroke="#F472B6" strokeWidth="2.2" />
          </svg>
          <span className={styles.brandWordmark}>INVESTINTEL</span>
        </button>

        <div className={styles.navRightActions}>
          <LanguageToggle variant="gateway" />
          <button
            type="button"
            className={styles.navDocsBtn}
            onClick={() => scrollToRef(roadmapSectionRef)}
          >
            {t("QUY TRÌNH", "PIPELINE")}
          </button>
          <button
            type="button"
            className={styles.navConnectBtn}
            onClick={() => triggerBreach()}
          >
            {t("TRUY CẬP", "CONNECT")}
          </button>
        </div>
      </header>

      <div className={styles.contentRoot}>
        {/* ================================================================
            SLIDE 1: HIGH-DETAIL COSMIC SPACE HERO (30+ Facet Planet, Moon, Asteroid Belt & Detailed Starfighter)
            ================================================================ */}
        <section className={styles.heroSection}>
          {/* High-Detail Top-Left Geodesic Ringed Planet */}
          <div ref={planetParallaxRef} className={styles.planetParallaxWrap} aria-hidden="true">
            <svg
              className={styles.planetTopLeft}
              viewBox="0 0 560 480"
              fill="none"
            >
            <defs>
              <radialGradient id="planetHalo" cx="60%" cy="46%" r="55%">
                <stop offset="0%" stopColor="#99F6E4" stopOpacity="0.68" />
                <stop offset="52%" stopColor="#3B82F6" stopOpacity="0.28" />
                <stop offset="100%" stopColor="#18103C" stopOpacity="0" />
              </radialGradient>
              <clipPath id="planetSphereClip">
                <circle cx="215" cy="185" r="154" />
              </clipPath>
            </defs>
            <circle cx="235" cy="195" r="235" fill="url(#planetHalo)" />
            {/* Back Half of Planetary Ring */}
            <g transform="rotate(14 215 190)">
              <path d="M 15 190 C 120 142, 315 140, 445 186 L 432 198 C 310 156, 125 158, 25 202 Z" fill="#6D28D9" opacity="0.6" />
            </g>
            {/* Geodesic Multi-Faceted Planet Sphere */}
            <g clipPath="url(#planetSphereClip)">
              <circle cx="215" cy="185" r="154" fill="#1E1B4B" />
              {/* Crown & Equatorial Bright Facets */}
              <polygon points="105,35 190,25 162,92" fill="#A855F7" />
              <polygon points="190,25 282,42 224,98" fill="#E879F9" />
              <polygon points="190,25 224,98 162,92" fill="#C084FC" />
              <polygon points="282,42 355,106 278,128" fill="#6EE7B7" />
              <polygon points="224,98 282,42 278,128" fill="#34D399" />
              <polygon points="162,92 224,98 188,162" fill="#818CF8" />
              <polygon points="224,98 278,128 248,186" fill="#5EEAD4" />
              <polygon points="188,162 224,98 248,186" fill="#38BDF8" />
              {/* Lower Illuminated Terminator Facets */}
              <polygon points="278,128 355,106 368,194" fill="#A5F3FC" stroke="rgba(255,255,255,0.28)" strokeWidth="0.8" />
              <polygon points="248,186 278,128 368,194" fill="#67E8F9" stroke="rgba(255,255,255,0.22)" strokeWidth="0.8" />
              <polygon points="248,186 368,194 316,278" fill="#99F6E4" opacity="0.92" stroke="rgba(165,243,252,0.25)" strokeWidth="0.8" />
              <polygon points="188,162 248,186 226,254" fill="#2563EB" stroke="rgba(165,243,252,0.18)" strokeWidth="0.7" />
              <polygon points="226,254 248,186 316,278" fill="#3B82F6" stroke="rgba(165,243,252,0.18)" strokeWidth="0.7" />
              {/* Deep Shadow Facets on Left & Bottom */}
              <polygon points="62,98 105,35 162,92" fill="#4338CA" />
              <polygon points="62,98 162,92 122,165" fill="#4F46E5" />
              <polygon points="122,165 162,92 188,162" fill="#3730A3" />
              <polygon points="62,98 122,165 55,205" fill="#312E81" />
              <polygon points="55,205 122,165 138,248" fill="#1E1B4B" />
              <polygon points="122,165 188,162 174,242" fill="#312E81" />
              <polygon points="174,242 188,162 226,254" fill="#4338CA" />
              <polygon points="138,248 174,242 226,254" fill="#1E1B4B" />
              <polygon points="138,248 226,254 198,332" fill="#271F5F" />
              <polygon points="226,254 316,278 242,338" fill="#4F46E5" />
              <polygon points="198,332 226,254 242,338" fill="#312E81" />
              {/* Geodesic Rim Wireframe Specular */}
              <polyline points="105,35 162,92 224,98 278,128 248,186 316,278" stroke="rgba(255,255,255,0.22)" strokeWidth="1" fill="none" />
            </g>
            {/* Front Multi-Band Low-Poly Ring + Orbiting Ring Shards */}
            <g transform="rotate(14 215 190)">
              <path
                d="M 12 204 C 122 266, 308 268, 456 202 L 474 224 C 314 294, 114 292, 2 224 Z"
                fill="#A5B4FC"
                opacity="0.9"
              />
              <path
                d="M 28 214 C 132 270, 306 272, 444 210"
                stroke="#E0E7FF"
                strokeWidth="1.5"
                opacity="0.65"
                fill="none"
              />
              <path
                d="M 48 220 C 148 268, 294 270, 424 216 L 434 226 C 296 280, 146 278, 38 230 Z"
                fill="#E0E7FF"
                opacity="0.85"
              />
              <polygon points="118,242 152,250 144,264 108,256" fill="#C4B5FD" />
              <polygon points="185,256 226,262 216,276 174,268" fill="#A5F3FC" />
              <polygon points="264,254 312,244 322,258 274,268" fill="#E0E7FF" />
              <polygon points="348,236 394,220 404,236 360,250" fill="#DDD6FE" />
              <polygon points="418,210 448,198 462,216 432,226" fill="#99F6E4" />
            </g>
            </svg>
          </div>

          {/* High-Detail Top-Right Fractured Cyan Moon + 14 Crystal Shards */}
          <div ref={moonParallaxRef} className={styles.moonParallaxWrap} aria-hidden="true">
            <svg
              className={styles.moonTopRight}
              viewBox="0 0 500 430"
              fill="none"
            >
            <defs>
              <radialGradient id="cyanMoonCoreGlow" cx="44%" cy="56%" r="54%">
                <stop offset="0%" stopColor="#67E8F9" stopOpacity="0.98" />
                <stop offset="46%" stopColor="#3B82F6" stopOpacity="0.4" />
                <stop offset="100%" stopColor="#18103C" stopOpacity="0" />
              </radialGradient>
            </defs>
            <circle cx="272" cy="195" r="165" fill="url(#cyanMoonCoreGlow)" className={styles.corePulse} />
            {/* Moon Outer Fractured Shell */}
            <circle cx="276" cy="192" r="108" fill="#251A57" />
            <polygon points="196,120 282,84 260,164" fill="#6D28D9" />
            <polygon points="282,84 366,136 312,188" fill="#4C1D95" />
            <polygon points="366,136 382,222 312,188" fill="#5B21B6" />
            <polygon points="312,188 382,222 332,286" fill="#3B0764" />
            <polygon points="172,186 248,162 214,232" fill="#312E81" />
            {/* Exposed Pulsing Cyan Crystal Core & Fissures */}
            <g className={styles.corePulse}>
              <polygon points="194,202 262,164 294,206 254,264 198,252" fill="#22D3EE" stroke="#A5F3FC" strokeWidth="1" />
              <polygon points="212,218 262,174 282,208 248,248" fill="#A5F3FC" />
              <polygon points="242,196 266,184 274,212 246,228" fill="#FFFFFF" opacity="0.95" />
              <polygon points="254,264 294,206 332,286 274,298" fill="#38BDF8" opacity="0.82" />
              <polyline points="262,164 246,228 274,298" stroke="#FFFFFF" strokeWidth="1.2" opacity="0.7" fill="none" />
              <polyline points="194,202 246,228 312,188" stroke="#A5F3FC" strokeWidth="1" opacity="0.6" fill="none" />
            </g>
            {/* Orbiting Crystal & Rock Shards */}
            <g className={styles.shardDriftSlow}>
              <polygon points="88,108 118,90 132,124 98,136" fill="#C4B5FD" />
              <polygon points="140,72 168,58 176,88 148,96" fill="#93C5FD" />
              <polygon points="74,264 106,248 118,284 82,292" fill="#A5F3FC" />
              <polygon points="122,306 146,294 156,322 128,330" fill="#67E8F9" />
              <polygon points="362,68 394,54 406,86 372,96" fill="#F9A8D4" />
              <polygon points="410,118 446,102 458,142 420,152" fill="#F472B6" />
              <polygon points="442,188 476,174 484,210 450,220" fill="#E879F9" />
            </g>
            <g className={styles.shardDriftFast}>
              <polygon points="384,254 416,238 428,274 390,284" fill="#F472B6" />
              <polygon points="326,318 358,304 370,336 332,344" fill="#C084FC" />
              <polygon points="274,344 302,332 310,360 282,368" fill="#A5F3FC" />
              <polygon points="154,206 172,196 178,220 158,224" fill="#FFFFFF" />
              <polygon points="196,62 216,52 222,74 200,80" fill="#A5F3FC" />
            </g>
            </svg>
          </div>

          {/* High-Detail Diagonal 3D Multi-Faceted Asteroid Belt */}
          <div ref={asteroidParallaxRef} className={styles.asteroidParallaxWrap} aria-hidden="true">
            <svg
              className={styles.asteroidDiagonal}
              viewBox="0 0 1440 900"
              preserveAspectRatio="none"
              fill="none"
            >
            {/* Large Left-Foreground Multi-Faceted Asteroid Cluster with Wireframe Seams & Crystal Veins */}
            <g className={styles.asteroidFloat1}>
              {/* Rock A1 (3 shaded planes + specular seam + cyan crystal vein) */}
              <polygon points="94,744 148,704 198,732 162,796 106,784" fill="#2A2056" stroke="rgba(165,243,252,0.22)" strokeWidth="1" />
              <polygon points="94,744 148,704 156,748 106,784" fill="#433485" />
              <polygon points="148,704 198,732 156,748" fill="#5B49A8" stroke="rgba(224,231,255,0.28)" strokeWidth="0.8" />
              <polygon points="156,748 198,732 162,796" fill="#1C143D" />
              <polygon points="134,740 156,728 160,746 138,754" fill="#67E8F9" opacity="0.82" />
              <polygon points="142,739 154,732 156,743" fill="#FFFFFF" opacity="0.7" />
              {/* Rock A2 */}
              <polygon points="218,684 268,656 302,684 276,728 228,718" fill="#271C52" stroke="rgba(196,181,253,0.22)" strokeWidth="0.9" />
              <polygon points="218,684 268,656 262,696" fill="#4B3B91" />
              <polygon points="262,696 302,684 276,728" fill="#171036" />
              <polygon points="256,676 274,668 278,684 260,688" fill="#F472B6" opacity="0.7" />
              {/* Rock A3 Foreground Small Crystal Rock */}
              <polygon points="34,826 78,798 112,832 82,866 42,856" fill="#312468" stroke="rgba(165,243,252,0.25)" strokeWidth="0.9" />
              <polygon points="34,826 78,798 76,834" fill="#6366F1" opacity="0.72" />
            </g>

            {/* Mid-Belt Asteroids Crossing Under Hero */}
            <g className={styles.asteroidFloat2}>
              <polygon points="338,634 390,606 424,638 386,678 346,664" fill="#24194E" stroke="rgba(196,181,253,0.22)" strokeWidth="0.9" />
              <polygon points="338,634 390,606 384,644" fill="#47378C" />
              <polygon points="384,644 424,638 386,678" fill="#160E34" />
              <polyline points="338,634 384,644 386,678" stroke="rgba(165,243,252,0.28)" strokeWidth="0.9" fill="none" />

              <polygon points="498,582 546,554 578,582 546,618 508,608" fill="#2A1D5A" stroke="rgba(249,168,212,0.24)" strokeWidth="0.9" />
              <polygon points="498,582 546,554 538,592" fill="#5442A3" />
              <polygon points="536,574 552,566 556,584 540,590" fill="#F472B6" opacity="0.78" />

              <polygon points="382,782 432,750 470,786 432,828 388,812" fill="#2D2060" stroke="rgba(165,243,252,0.2)" strokeWidth="0.9" />
              <polygon points="382,782 432,750 426,792" fill="#5240A0" />
              <polygon points="426,792 470,786 432,828" fill="#1A113F" />
            </g>

            {/* Upper-Right Asteroid Belt Ascending Into Fractured Moon */}
            <g className={styles.asteroidFloat1}>
              <polygon points="718,484 762,462 786,492 752,516 724,504" fill="#24184E" stroke="rgba(196,181,253,0.22)" strokeWidth="0.8" />
              <polygon points="718,484 762,462 754,492" fill="#4D3B94" />

              <polygon points="932,374 982,348 1014,380 976,412 940,398" fill="#291B57" stroke="rgba(165,243,252,0.24)" strokeWidth="0.9" />
              <polygon points="932,374 982,348 972,384" fill="#5C48AD" />
              <polygon points="972,384 1014,380 976,412" fill="#19103B" />
              <polygon points="960,368 978,360 982,374 964,378" fill="#67E8F9" opacity="0.65" />

              <polygon points="1084,296 1134,272 1168,302 1130,334 1094,320" fill="#211548" stroke="rgba(249,168,212,0.22)" strokeWidth="0.9" />
              <polygon points="1084,296 1134,272 1126,306" fill="#4E3A99" />

              <polygon points="1186,238 1224,218 1246,244 1216,268 1192,256" fill="#312066" stroke="rgba(165,243,252,0.3)" strokeWidth="0.9" />
              <polygon points="1186,238 1224,218 1218,248" fill="#A5F3FC" opacity="0.68" />
            </g>
            </svg>
          </div>

          {/* High-Detail Bottom-Right Sci-Fi Low-Poly Starfighter with Shock-Diamond Ion Thrusters */}
          <svg
            className={styles.spaceshipBottomRight}
            viewBox="0 0 400 265"
            fill="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="hullMetal" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6366F1" />
                <stop offset="45%" stopColor="#312E81" />
                <stop offset="100%" stopColor="#1E1B4B" />
              </linearGradient>
              <linearGradient id="innerNozzle" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#09071A" />
                <stop offset="100%" stopColor="#38BDF8" stopOpacity="0.85" />
              </linearGradient>
              <linearGradient id="plasmaOuter" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#38BDF8" stopOpacity="0.92" />
                <stop offset="42%" stopColor="#EC4899" stopOpacity="0.68" />
                <stop offset="100%" stopColor="#8B5CF6" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="plasmaMid" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#67E8F9" stopOpacity="0.98" />
                <stop offset="50%" stopColor="#F472B6" stopOpacity="0.85" />
                <stop offset="100%" stopColor="#A855F7" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="plasmaCore" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#FFFFFF" stopOpacity="1" />
                <stop offset="55%" stopColor="#A5F3FC" stopOpacity="0.92" />
                <stop offset="100%" stopColor="#38BDF8" stopOpacity="0" />
              </linearGradient>
              <radialGradient id="thrusterAura" cx="42%" cy="46%" r="58%">
                <stop offset="0%" stopColor="#A5F3FC" stopOpacity="0.85" />
                <stop offset="40%" stopColor="#F472B6" stopOpacity="0.45" />
                <stop offset="100%" stopColor="#312E81" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Atmospheric Engine Exhaust Bloom */}
            <circle cx="298" cy="186" r="82" fill="url(#thrusterAura)" />

            {/* Dual Multi-Segment Supersonic Plasma Plumes + 5 Shock Diamonds (Mach Disks) */}
            <g className={styles.thrusterFlame}>
              {/* Upper Right Nozzle Plume */}
              <polygon points="252,156 382,224 285,138" fill="#EC4899" opacity="0.22" />
              <polygon points="256,154 374,218 282,140" fill="url(#plasmaOuter)" />
              <polygon points="258,155 348,202 280,144" fill="url(#plasmaMid)" />
              <polygon points="260,156 318,184 276,148" fill="url(#plasmaCore)" />
              {/* Lower Left Nozzle Plume */}
              <polygon points="218,172 346,248 254,152" fill="#EC4899" opacity="0.22" />
              <polygon points="222,170 338,242 252,154" fill="url(#plasmaOuter)" />
              <polygon points="226,170 314,224 248,158" fill="url(#plasmaMid)" />
              <polygon points="230,170 288,202 244,162" fill="url(#plasmaCore)" />
              {/* Supersonic Shock Diamonds (Mach Disks) */}
              <g className={styles.shockDiamonds}>
                {/* Upper stream Mach disks */}
                <polygon points="274,157 283,155 289,163 280,165" fill="#FFFFFF" />
                <polygon points="295,168 303,167 308,174 300,175" fill="#A5F3FC" opacity="0.92" />
                <polygon points="315,179 322,178 326,184 319,185" fill="#F9A8D4" opacity="0.82" />
                {/* Lower stream Mach disks */}
                <polygon points="242,173 251,171 257,179 248,181" fill="#FFFFFF" />
                <polygon points="264,186 272,185 277,192 269,193" fill="#A5F3FC" opacity="0.9" />
                <polygon points="285,199 292,198 296,204 289,205" fill="#F9A8D4" opacity="0.78" />
              </g>
            </g>

            {/* Twin Sculpted Metallic Engine Nozzles + Glowing Core Throats */}
            <polygon points="242,146 276,140 270,162 238,164" fill="url(#hullMetal)" stroke="#A5B4FC" strokeWidth="0.9" />
            <ellipse cx="268" cy="152" rx="6" ry="8.5" transform="rotate(-18 268 152)" fill="url(#innerNozzle)" stroke="#67E8F9" strokeWidth="1.2" />
            <polygon points="214,160 246,154 242,176 210,178" fill="url(#hullMetal)" stroke="#818CF8" strokeWidth="0.9" />
            <ellipse cx="238" cy="167" rx="6" ry="8.5" transform="rotate(-18 238 167)" fill="url(#innerNozzle)" stroke="#67E8F9" strokeWidth="1.2" />

            {/* Far Wing + Micro Missile Rail + Magenta Nav Strobe */}
            <polygon points="92,74 268,118 244,144 134,108" fill="#A5B4FC" stroke="rgba(255,255,255,0.45)" strokeWidth="0.8" />
            <polygon points="154,92 268,118 244,132" fill="#E0E7FF" />
            <line x1="168" y1="98" x2="254" y2="122" stroke="#67E8F9" strokeWidth="1.2" opacity="0.85" />
            <circle cx="270" cy="119" r="5.5" fill="#F472B6" opacity="0.28" />
            <circle cx="270" cy="119" r="3.2" fill="#F472B6" />

            {/* Main Fuselage Multi-Shaded Facets + Panel Seams + Glowing Conduits */}
            <polygon points="24,46 168,104 148,128 84,96" fill="#FFFFFF" stroke="rgba(165,180,252,0.5)" strokeWidth="0.8" />
            <polygon points="24,46 84,96 112,126" fill="#C7D2FE" />
            <polygon points="168,104 252,138 228,158 148,128" fill="#E0E7FF" />
            <polygon points="148,128 228,158 188,184 128,152" fill="#818CF8" />
            {/* Fuselage Nose Intake & Panel Detail Lines */}
            <line x1="48" y1="58" x2="152" y2="104" stroke="#6366F1" strokeWidth="1.1" opacity="0.65" />
            <line x1="164" y1="114" x2="236" y2="144" stroke="#22D3EE" strokeWidth="1.8" opacity="0.92" />
            <polygon points="74,78 96,86 90,94 68,84" fill="#312E81" />

            {/* Lower Swept Near-Wing + Glowing Intake Stripe + Cyan Nav Strobe */}
            <polygon points="118,128 198,164 176,198 112,158" fill="#6366F1" stroke="rgba(224,231,255,0.4)" strokeWidth="0.8" />
            <polygon points="118,128 176,198 152,202 104,152" fill="#4338CA" />
            <polygon points="118,136 170,178 154,186 112,146" fill="#F472B6" opacity="0.88" />
            <line x1="126" y1="148" x2="170" y2="188" stroke="#A5F3FC" strokeWidth="1.4" opacity="0.9" />
            <circle cx="176" cy="198" r="5.5" fill="#67E8F9" opacity="0.28" />
            <circle cx="176" cy="198" r="3.2" fill="#67E8F9" />

            {/* Illuminated Cockpit Canopy with HUD Reflection Glint */}
            <polygon points="108,82 172,108 158,124 122,110" fill="#0284C7" stroke="#A5F3FC" strokeWidth="0.9" />
            <polygon points="116,86 164,106 154,116 126,104" fill="#38BDF8" />
            <polygon points="122,88 154,102 148,106 126,96" fill="#FFFFFF" opacity="0.9" />

            {/* Dorsal Fin Stabilizer */}
            <polygon points="190,118 244,104 236,138" fill="#C4B5FD" stroke="rgba(255,255,255,0.45)" strokeWidth="0.8" />
            <polygon points="190,118 244,104 218,126" fill="#FFFFFF" />

            {/* Animated Supersonic Plasma Spark Trail */}
            <g className={styles.sparkStream}>
              <polygon points="334,148 346,142 342,154" fill="#F9A8D4" />
              <polygon points="356,178 370,172 366,186" fill="#67E8F9" />
              <polygon points="326,218 340,212 336,224" fill="#A5F3FC" />
              <polygon points="374,204 384,198 382,210" fill="#FFFFFF" />
              <polygon points="296,236 308,230 304,242" fill="#F472B6" />
            </g>
          </svg>

          {/* Hero Copy & CTA Row */}
          <div className={styles.heroCenterContent}>
            <span className={styles.eyebrowCaption}>
              {t("GIỚI THIỆU NỀN TẢNG", "INTRODUCING")}
            </span>
            <h1 className={styles.slantedHeroTitle}>INVESTINTEL</h1>
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
                className={styles.pinkChamferBtn}
                onClick={() => scrollToRef(whySectionRef)}
              >
                {t("KHÁM PHÁ", "DISCOVER")}
              </button>
              <button
                type="button"
                className={styles.whiteRectBtn}
                onClick={() => triggerBreach()}
              >
                {t("ĐẦU TƯ", "INVEST")}
              </button>
            </div>
          </div>

          <button
            type="button"
            className={styles.scrollDownPrompt}
            onClick={() => scrollToRef(whySectionRef)}
          >
            {t(
              "CUỘN XUỐNG ĐỂ KHÁM PHÁ CÁC PHÂN HỆ ĐỊNH LƯỢNG & PHÂN TÍCH AI CHUYÊN SÂU",
              "SCROLL DOWN TO EXPLORE OUR QUANTITATIVE & EVIDENCE-FIRST AI MODULES"
            )}
          </button>
        </section>

        {/* ================================================================
            SLIDE 2: WHY INVESTINTEL? + OUR PRODUCTS SUNSET MOUNTAIN HORIZON
            ================================================================ */}
        <section ref={whySectionRef} className={styles.whyAndProductsSection}>
          {/* Central data spine continuing from the hero scroll prompt */}
          <span className={`${styles.spineConnector} ${styles.spineConnectorTop}`} aria-hidden="true" />

          <div className={`${styles.whyBlock} ${styles.revealBlock}`} data-reveal>
            <h2 className={styles.slantedSectionTitle}>
              {t("VÌ SAO CHỌN INVESTINTEL?", "WHY INVESTINTEL?")}
            </h2>
            <p className={styles.whyBody}>
              {t(
                "InvestIntel thu hẹp khoảng cách giữa dữ liệu tài chính phân mảnh và chuẩn mực phân tích định lượng tổ chức tại Việt Nam. Toàn bộ quy trình dữ liệu lịch sử theo đúng mốc thời gian (HOSE, HNX, UPCOM), điều chỉnh EPS theo IAS 33, chấm điểm đa nhân tố VN100 và đối soát báo cáo tài chính bằng AI trích dẫn nguồn gốc được hợp nhất trên một trạm làm việc đồng bộ.",
                "InvestIntel bridges the gap between fragmented local market feeds and institutional quantitative research standards in Vietnam. Point-in-Time EOD pricing, IAS 33 corporate-action normalization, multi-factor VN100 scoring, and citation-locked AI statement verification operate together in one unified workstation."
              )}
            </p>

            <div className={styles.whyStatsGrid}>
              {whyStats.map((stat, idx) => (
                <div
                  key={stat.label}
                  className={`${styles.whyStatTile} ${styles.revealBlock}`}
                  data-reveal
                  style={{ "--reveal-delay": `${120 + idx * 80}ms` } as React.CSSProperties}
                >
                  <span className={styles.whyStatValue}>{stat.value}</span>
                  <span className={styles.whyStatLabel}>{stat.label}</span>
                </div>
              ))}
            </div>

            <button
              type="button"
              className={styles.whiteRectBtn}
              onClick={() => scrollToRef(roadmapSectionRef)}
            >
              {t("XEM QUY TRÌNH", "READ MORE")}
            </button>
            <span className={styles.spineConnector} aria-hidden="true" />
          </div>

          <div className={styles.productsHorizonWrapper}>
            {/* High-Detail Sunset Mountain Horizon + Crystal Spires + Hovering Scout Pods + Lake Outflow River */}
            <svg
              className={styles.horizonBackdropSvg}
              viewBox="0 0 1440 760"
              preserveAspectRatio="none"
              fill="none"
              aria-hidden="true"
            >
              <defs>
                <radialGradient id="sunriseGlow" cx="30%" cy="60%" r="50%">
                  <stop offset="0%" stopColor="#FEF08A" stopOpacity="0.96" />
                  <stop offset="32%" stopColor="#F9A8D4" stopOpacity="0.68" />
                  <stop offset="100%" stopColor="#6D459E" stopOpacity="0" />
                </radialGradient>
                <linearGradient id="planetHorizon" x1="0" y1="0" x2="1" y2="1">
                  <stop offset="0%" stopColor="#A5F3FC" stopOpacity="0.82" />
                  <stop offset="100%" stopColor="#6366F1" stopOpacity="0.32" />
                </linearGradient>
                <linearGradient id="lakeShimmer" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#3B0764" stopOpacity="0" />
                  <stop offset="50%" stopColor="#F9A8D4" stopOpacity="0.52" />
                  <stop offset="100%" stopColor="#3B0764" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="auroraGrad" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#67E8F9" stopOpacity="0" />
                  <stop offset="30%" stopColor="#67E8F9" stopOpacity="0.38" />
                  <stop offset="62%" stopColor="#C084FC" stopOpacity="0.42" />
                  <stop offset="100%" stopColor="#F472B6" stopOpacity="0" />
                </linearGradient>
                <linearGradient id="shootGrad" x1="980" y1="0" x2="1080" y2="0" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0" />
                  <stop offset="100%" stopColor="#FFFFFF" stopOpacity="0.95" />
                </linearGradient>
                {/* Outflow river gradients end on the exact colors where Slide 3's river begins */}
                <linearGradient id="outflowOuter" x1="720" y1="610" x2="720" y2="760" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#F472B6" stopOpacity="0" />
                  <stop offset="45%" stopColor="#C084FC" stopOpacity="0.2" />
                  <stop offset="100%" stopColor="#60A5FA" stopOpacity="0.22" />
                </linearGradient>
                <linearGradient id="outflowBody" x1="720" y1="610" x2="720" y2="760" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#F9A8D4" stopOpacity="0" />
                  <stop offset="40%" stopColor="#C4B5FD" stopOpacity="0.6" />
                  <stop offset="100%" stopColor="#93C5FD" stopOpacity="0.7" />
                </linearGradient>
                <linearGradient id="outflowCore" x1="720" y1="610" x2="720" y2="760" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#FBCFE8" stopOpacity="0" />
                  <stop offset="50%" stopColor="#F5D0FE" stopOpacity="0.32" />
                  <stop offset="100%" stopColor="#E0E7FF" stopOpacity="0.35" />
                </linearGradient>
                <linearGradient id="outflowDash" x1="720" y1="610" x2="720" y2="760" gradientUnits="userSpaceOnUse">
                  <stop offset="0%" stopColor="#FFFFFF" stopOpacity="0" />
                  <stop offset="55%" stopColor="#FFFFFF" stopOpacity="1" />
                  <stop offset="100%" stopColor="#FFFFFF" stopOpacity="1" />
                </linearGradient>
                <radialGradient id="lakeSourceGlow" cx="50%" cy="50%" r="50%">
                  <stop offset="0%" stopColor="#FBCFE8" stopOpacity="0.7" />
                  <stop offset="55%" stopColor="#C084FC" stopOpacity="0.25" />
                  <stop offset="100%" stopColor="#1B0F42" stopOpacity="0" />
                </radialGradient>
              </defs>

              <rect width="1440" height="760" fill="url(#sunriseGlow)" className={styles.sunPulseGroup} />
              {/* Crescent Moon Behind Left Ridge */}
              <circle cx="176" cy="445" r="175" fill="url(#planetHorizon)" opacity="0.56" />

              {/* Aurora Ribbon Across the Upper Sky */}
              <path
                className={styles.auroraWave}
                d="M 0 236 C 220 176, 420 262, 660 214 C 900 166, 1120 250, 1440 196 L 1440 226 C 1140 282, 900 200, 660 248 C 420 296, 220 210, 0 268 Z"
                fill="url(#auroraGrad)"
              />

              {/* Distant Ringed Planet */}
              <g className={styles.distantPlanet}>
                <circle cx="1046" cy="252" r="22" fill="#C4B5FD" opacity="0.85" />
                <path d="M 1024 252 A 22 22 0 0 1 1068 252 Z" fill="#E0E7FF" opacity="0.55" />
                <ellipse cx="1046" cy="254" rx="40" ry="8" stroke="#F9A8D4" strokeWidth="2" opacity="0.75" fill="none" />
              </g>

              {/* Shooting Star */}
              <g className={styles.shootingStar}>
                <line x1="980" y1="210" x2="1080" y2="178" stroke="url(#shootGrad)" strokeWidth="2.2" strokeLinecap="round" />
                <circle cx="1080" cy="178" r="2.6" fill="#FFFFFF" />
              </g>

              {/* Animated Drifting Low-Poly Sunset Clouds */}
              <g className={styles.cloudLeft}>
                <polygon points="86,184 260,152 440,174 560,192 296,214 134,204" fill="#A78BFA" opacity="0.46" />
                <polygon points="210,164 380,148 486,178 272,188" fill="#DDD6FE" opacity="0.3" />
              </g>
              <g className={styles.cloudRight}>
                <polygon points="824,162 1046,136 1264,148 1420,182 1068,202" fill="#8B5CF6" opacity="0.42" />
                <polygon points="940,152 1190,136 1310,168 1020,176" fill="#F5D0FE" opacity="0.24" />
              </g>

              {/* Distant & Mid Multi-Ridged Low-Poly Mountains with Specular Rim Seams */}
              <polygon points="540,580 760,430 870,500 1010,410 1190,580" fill="#5E3F99" opacity="0.55" stroke="rgba(224,231,255,0.16)" strokeWidth="0.9" />
              <polygon points="760,430 870,500 820,580 1010,410 1190,580" fill="#4A2F82" opacity="0.5" />
              <polygon points="430,580 680,458 920,580" fill="#7C54AD" opacity="0.72" stroke="rgba(224,231,255,0.22)" strokeWidth="0.9" />
              <polygon points="680,458 920,580 730,580" fill="#5B3B8D" opacity="0.78" />
              <polyline points="430,580 680,458 920,580" stroke="rgba(249,168,212,0.32)" strokeWidth="1" fill="none" />

              {/* Left Jagged Mountain Peak */}
              <polygon points="0,580 185,305 340,420 515,580" fill="#47367F" stroke="rgba(165,243,252,0.22)" strokeWidth="1" />
              <polygon points="185,305 340,420 264,580 515,580" fill="#2E215E" />
              <polygon points="185,305 232,374 128,450" fill="#634B9E" opacity="0.78" />
              <polygon points="185,305 206,336 168,330" fill="#E0E7FF" opacity="0.7" />
              <polyline points="0,580 185,305 340,420 515,580" stroke="rgba(249,168,212,0.28)" strokeWidth="1.2" fill="none" />

              {/* Right Jagged Mountain Range */}
              <polygon points="900,580 1125,382 1285,250 1440,382 1440,580" fill="#4E388C" stroke="rgba(165,243,252,0.2)" strokeWidth="1" />
              <polygon points="1285,250 1440,382 1440,580 1165,580" fill="#2D1E5E" />
              <polygon points="1125,382 1285,250 1245,425" fill="#7158B5" opacity="0.72" />
              <polygon points="1285,250 1310,272 1262,280" fill="#E0E7FF" opacity="0.68" />
              <polyline points="900,580 1125,382 1285,250 1440,382" stroke="rgba(165,243,252,0.28)" strokeWidth="1.2" fill="none" />

              {/* Shimmering Sunset Horizon Lake */}
              <rect x="0" y="580" width="1440" height="180" fill="#1B0F42" />
              <polygon points="310,580 1110,580 990,654 430,654" fill="url(#lakeShimmer)" />
              <line x1="480" y1="600" x2="940" y2="600" stroke="#FDE68A" strokeWidth="2" opacity="0.45" />
              <line x1="540" y1="616" x2="880" y2="616" stroke="#F9A8D4" strokeWidth="1.5" opacity="0.35" />
              <g className={styles.lakeRipples}>
                <line x1="250" y1="676" x2="430" y2="676" stroke="#C4B5FD" strokeWidth="1.2" opacity="0.4" />
                <line x1="980" y1="684" x2="1180" y2="684" stroke="#C4B5FD" strokeWidth="1.2" opacity="0.4" />
                <line x1="120" y1="712" x2="260" y2="712" stroke="#A5F3FC" strokeWidth="1" opacity="0.32" />
                <line x1="1220" y1="726" x2="1380" y2="726" stroke="#A5F3FC" strokeWidth="1" opacity="0.32" />
              </g>

              {/* Lake Source Glow + Outflow River (continues seamlessly into Slide 3 river) */}
              <ellipse cx="720" cy="640" rx="190" ry="34" fill="url(#lakeSourceGlow)" className={styles.sunPulseGroup} />
              <path d="M 720 612 L 720 800" stroke="url(#outflowOuter)" className={styles.riverGlowStroke} vectorEffect="non-scaling-stroke" strokeLinecap="butt" />
              <path d="M 720 612 L 720 800" stroke="url(#outflowBody)" className={styles.riverBodyStroke} vectorEffect="non-scaling-stroke" strokeLinecap="butt" />
              <path d="M 720 612 L 720 800" stroke="url(#outflowCore)" className={styles.riverCoreStroke} vectorEffect="non-scaling-stroke" strokeLinecap="butt" />
              <path d="M 720 612 L 720 800" stroke="url(#outflowDash)" className={`${styles.riverDashStroke} ${styles.riverCurrentStream}`} vectorEffect="non-scaling-stroke" strokeLinecap="round" />

              {/* Left Futuristic Crystal Spire & Lattice Citadel */}
              <polygon points="48,650 96,315 144,650" fill="#4F46E5" opacity="0.88" />
              <polygon points="96,315 144,650 112,650" fill="#7DD3FC" opacity="0.92" />
              <rect x="92" y="345" width="7" height="285" fill="#A5F3FC" className={styles.towerConduit} />
              <circle cx="96" cy="312" r="4" fill="#F472B6" className={styles.beaconBlink} />

              <polygon points="168,660 168,530 438,510 438,660" fill="#312468" />
              <line x1="176" y1="538" x2="432" y2="652" stroke="#67E8F9" strokeWidth="4.5" className={styles.towerConduit} />
              <line x1="176" y1="564" x2="424" y2="554" stroke="#818CF8" strokeWidth="1.2" opacity="0.55" />
              <line x1="176" y1="596" x2="424" y2="590" stroke="#818CF8" strokeWidth="1.2" opacity="0.55" />
              <line x1="176" y1="628" x2="424" y2="624" stroke="#818CF8" strokeWidth="1.2" opacity="0.45" />
              {/* Citadel Window Grid */}
              <rect x="196" y="572" width="10" height="5" fill="#FDE68A" opacity="0.75" />
              <rect x="226" y="606" width="10" height="5" fill="#A5F3FC" opacity="0.7" />
              <rect x="372" y="572" width="10" height="5" fill="#F9A8D4" opacity="0.7" />
              <rect x="398" y="606" width="10" height="5" fill="#FDE68A" opacity="0.7" />
              {/* Satellite Uplink Dish on Citadel Roof */}
              <line x1="318" y1="518" x2="318" y2="490" stroke="#A5B4FC" strokeWidth="2" />
              <path d="M 296 488 Q 318 470 340 488 Z" fill="#C7D2FE" stroke="#E0E7FF" strokeWidth="1" />
              <line x1="318" y1="482" x2="330" y2="466" stroke="#E0E7FF" strokeWidth="1.2" />
              <circle cx="331" cy="464" r="3" fill="#67E8F9" className={styles.beaconBlink} />

              {/* Right Stepped Pyramid Citadel + Tall Skyscraper Monolith */}
              <polygon points="1018,658 1102,462 1202,462 1280,658" fill="#5B49A8" />
              <polygon points="1060,560 1240,560 1250,580 1050,580" fill="#4B3B91" opacity="0.8" />
              <polygon points="1136,658 1144,462 1172,462 1180,658" fill="#A5F3FC" className={styles.towerConduit} />
              <circle cx="1158" cy="458" r="4" fill="#67E8F9" className={styles.beaconBlink} />
              <polygon points="1270,658 1270,295 1372,295 1372,658" fill="#4338CA" />
              <polygon points="1270,295 1321,262 1372,295" fill="#6366F1" />
              <line x1="1321" y1="262" x2="1321" y2="232" stroke="#C7D2FE" strokeWidth="2" />
              <circle cx="1321" cy="230" r="4.5" fill="#F472B6" className={styles.beaconBlink} />
              <rect x="1310" y="315" width="18" height="325" fill="#A5F3FC" className={styles.towerConduit} />
              {/* Lit Tower Window Arrays */}
              <rect x="1282" y="340" width="18" height="4" fill="#E0E7FF" opacity="0.7" />
              <rect x="1282" y="356" width="14" height="4" fill="#67E8F9" opacity="0.85" />
              <rect x="1336" y="374" width="20" height="4" fill="#F9A8D4" opacity="0.75" />
              <rect x="1282" y="408" width="16" height="4" fill="#E0E7FF" opacity="0.7" />
              <rect x="1336" y="438" width="22" height="4" fill="#67E8F9" opacity="0.85" />
              <rect x="1282" y="472" width="18" height="4" fill="#F9A8D4" opacity="0.7" />
              <rect x="1336" y="508" width="16" height="4" fill="#E0E7FF" opacity="0.7" />
              <rect x="1282" y="546" width="14" height="4" fill="#67E8F9" opacity="0.8" />

              {/* Lake Reflections of the Towers */}
              <g className={styles.lakeRipples}>
                <rect x="1270" y="662" width="102" height="64" fill="#4338CA" opacity="0.2" />
                <rect x="1310" y="662" width="18" height="78" fill="#A5F3FC" opacity="0.22" />
                <rect x="1136" y="662" width="44" height="52" fill="#A5F3FC" opacity="0.16" />
                <rect x="92" y="654" width="7" height="70" fill="#A5F3FC" opacity="0.2" />
              </g>

              {/* Autonomous Hovering Scout Pods with Twin Thruster Micro-Plumes */}
              <g className={styles.podHoverA}>
                <polygon points="242,472 268,464 294,472 268,479" fill="#E0E7FF" />
                <ellipse cx="268" cy="472" rx="18" ry="4.5" fill="#818CF8" />
                <ellipse cx="268" cy="475" rx="12" ry="2.8" fill="#67E8F9" />
                <polygon points="256,476 260,484 264,476" fill="#A5F3FC" opacity="0.85" />
                <polygon points="272,476 276,484 280,476" fill="#A5F3FC" opacity="0.85" />
              </g>
              <g className={styles.podHoverB}>
                <polygon points="918,494 945,485 972,494 945,501" fill="#DDD6FE" />
                <ellipse cx="945" cy="494" rx="20" ry="4.5" fill="#C084FC" />
                <ellipse cx="945" cy="497" rx="13" ry="2.8" fill="#F472B6" />
                <polygon points="932,498 936,506 940,498" fill="#F9A8D4" opacity="0.85" />
                <polygon points="950,498 954,506 958,498" fill="#F9A8D4" opacity="0.85" />
              </g>
              <g className={styles.podHoverA}>
                <polygon points="1176,378 1196,372 1216,378 1196,383" fill="#E0E7FF" />
                <ellipse cx="1196" cy="378" rx="14" ry="3.5" fill="#67E8F9" />
                <polygon points="1190,382 1193,389 1196,382" fill="#A5F3FC" opacity="0.8" />
              </g>

              {/* Low-Poly Teal Pine Clusters */}
              <polygon points="148,712 172,605 196,712" fill="#0F766E" />
              <polygon points="182,718 202,628 222,718" fill="#14B8A6" />
              <polygon points="212,722 228,650 244,722" fill="#0D9488" />
              <polygon points="562,710 584,616 606,710" fill="#0D9488" />
              <polygon points="530,716 548,646 566,716" fill="#0F766E" />
              <polygon points="872,712 892,630 912,712" fill="#0F766E" />
              <polygon points="902,718 918,654 934,718" fill="#14B8A6" />
              <polygon points="1018,712 1040,602 1062,712" fill="#0F766E" />
              <polygon points="1352,718 1378,598 1404,718" fill="#115E59" />
              <polygon points="1396,722 1414,640 1432,722" fill="#0D9488" />

              {/* Shoreline Fireflies */}
              <g className={styles.fireflyDrift}>
                <circle cx="300" cy="690" r="2.2" fill="#FDE68A" />
                <circle cx="460" cy="702" r="1.8" fill="#A5F3FC" />
                <circle cx="620" cy="690" r="2" fill="#F9A8D4" />
                <circle cx="840" cy="696" r="2" fill="#FDE68A" />
                <circle cx="1000" cy="706" r="1.8" fill="#A5F3FC" />
                <circle cx="1240" cy="694" r="2.2" fill="#F9A8D4" />
              </g>
            </svg>

            <div className={`${styles.productsCardContent} ${styles.revealBlock}`} data-reveal>
              <div
                className={styles.productTabs}
                role="tablist"
                aria-label={t("Chọn phân hệ sản phẩm", "Select product showcase")}
              >
                {productShowcases.map((prod, idx) => (
                  <button
                    key={prod.id}
                    type="button"
                    role="tab"
                    aria-selected={idx === productIndex}
                    className={`${styles.productTab} ${idx === productIndex ? styles.productTabActive : ""}`}
                    onClick={() => setProductIndex(idx)}
                  >
                    <span className={styles.productTabIndex}>{prod.index}</span>
                    <span className={styles.productTabLabel}>{prod.shortLabel}</span>
                  </button>
                ))}
              </div>

              <div key={activeProduct.id} className={styles.productSwapWrap}>
                <span className={styles.eyebrowCaption}>
                  {activeProduct.eyebrow} · {activeProduct.index}/{String(productShowcases.length).padStart(2, "0")}
                </span>
                <h2 className={styles.slantedSectionTitle}>{activeProduct.title}</h2>
                <span className={styles.pinkDashDivider} aria-hidden="true" />
                <p className={styles.productDesc}>{activeProduct.desc}</p>
                <ul className={styles.productSpecList}>
                  {activeProduct.specs.map((spec) => (
                    <li key={spec} className={styles.productSpecChip}>
                      <span className={styles.productSpecDot} aria-hidden="true" />
                      {spec}
                    </li>
                  ))}
                </ul>
              </div>
              <div className={styles.ctaRow}>
                <button
                  type="button"
                  className={styles.pinkChamferBtn}
                  onClick={() => triggerBreach(activeProduct.route)}
                >
                  {activeProduct.ctaLabel}
                </button>
                <button
                  type="button"
                  className={styles.whiteRectBtn}
                  onClick={() =>
                    setProductIndex((prev) => (prev + 1) % productShowcases.length)
                  }
                >
                  {t("TIẾP THEO ↗", "NEXT ↗")}
                </button>
              </div>
              <span className={styles.spineConnector} aria-hidden="true" />
            </div>
          </div>
        </section>

        {/* ================================================================
            SLIDE 3: WINDING RIVER VALLEY, CARDS 06-01 WITH PEARL ORBS & END-OF-ROAD PORTAL
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
              <linearGradient id="valleyTopFade" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#1B0F42" stopOpacity="1" />
                <stop offset="100%" stopColor="#1B0F42" stopOpacity="0" />
              </linearGradient>
              <linearGradient id="riverOuterGlow" x1="720" y1="-40" x2="720" y2="1525" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#60A5FA" stopOpacity="0.22" />
                <stop offset="50%" stopColor="#C084FC" stopOpacity="0.34" />
                <stop offset="100%" stopColor="#F472B6" stopOpacity="0.48" />
              </linearGradient>
              <linearGradient id="riverGrad" x1="720" y1="-40" x2="720" y2="1525" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#93C5FD" stopOpacity="0.7" />
                <stop offset="40%" stopColor="#C4B5FD" stopOpacity="0.88" />
                <stop offset="78%" stopColor="#F9A8D4" stopOpacity="0.95" />
                <stop offset="100%" stopColor="#F472B6" stopOpacity="0.98" />
              </linearGradient>
              <linearGradient id="riverCoreGrad" x1="720" y1="-40" x2="720" y2="1525" gradientUnits="userSpaceOnUse">
                <stop offset="0%" stopColor="#E0E7FF" stopOpacity="0.35" />
                <stop offset="55%" stopColor="#F5D0FE" stopOpacity="0.52" />
                <stop offset="100%" stopColor="#FBCFE8" stopOpacity="0.72" />
              </linearGradient>
              <radialGradient id="riverEndNexusGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#A5F3FC" stopOpacity="0.88" />
                <stop offset="45%" stopColor="#F472B6" stopOpacity="0.48" />
                <stop offset="100%" stopColor="#241459" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="lanternGlow" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#FDE68A" stopOpacity="0.9" />
                <stop offset="60%" stopColor="#F472B6" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#F472B6" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Lake continuation from Slide 2 so the boundary disappears */}
            <rect x="0" y="0" width="1440" height="150" fill="url(#valleyTopFade)" />

            {/* Distant Valley Ridge Silhouettes */}
            <polygon points="0,250 110,176 210,226 320,150 430,236 520,300 0,300" fill="#2A1A63" opacity="0.7" />
            <polygon points="920,300 1010,214 1120,262 1240,168 1340,232 1440,190 1440,300" fill="#2A1A63" opacity="0.7" />
            <polyline points="0,250 110,176 210,226 320,150 430,236 520,300" stroke="rgba(165,243,252,0.2)" strokeWidth="1" fill="none" />
            <polyline points="920,300 1010,214 1120,262 1240,168 1340,232 1440,190" stroke="rgba(249,168,212,0.22)" strokeWidth="1" fill="none" />

            {/* Winding River: starts vertically at the top-center where Slide 2's lake outflow ends */}
            <path
              d="M 720 -40 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1525"
              stroke="url(#riverOuterGlow)"
              className={styles.riverGlowStroke}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 720 -40 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1525"
              stroke="url(#riverGrad)"
              className={styles.riverBodyStroke}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M 720 -40 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1525"
              stroke="url(#riverCoreGrad)"
              className={styles.riverCoreStroke}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            {/* Static Crisp Dashed Centerline + Composite Pulsing Energy Nodes (Zero SVG Stroke Repaint) */}
            <path
              d="M 720 -40 L 720 40 C 720 150, 640 190, 640 320 C 640 465, 1000 490, 955 675 C 910 860, 355 855, 375 1065 C 395 1255, 695 1310, 720 1525"
              stroke="#FFFFFF"
              className={`${styles.riverDashStroke} ${styles.riverCurrentStream}`}
              vectorEffect="non-scaling-stroke"
              strokeLinecap="round"
              strokeLinejoin="round"
            />

            {/* River Surface Sparkles */}
            <g className={styles.riverSparkleA}>
              <polygon points="712,96 718,88 724,96 718,104" fill="#FFFFFF" />
              <polygon points="694,420 700,412 706,420 700,428" fill="#E0E7FF" />
              <polygon points="926,782 932,774 938,782 932,790" fill="#FFFFFF" />
              <polygon points="456,960 462,952 468,960 462,968" fill="#F5D0FE" />
              <polygon points="556,1330 562,1322 568,1330 562,1338" fill="#FFFFFF" />
            </g>
            <g className={styles.riverSparkleB}>
              <polygon points="660,214 666,206 672,214 666,222" fill="#A5F3FC" />
              <polygon points="872,556 878,548 884,556 878,564" fill="#FFFFFF" />
              <polygon points="706,880 712,872 718,880 712,888" fill="#A5F3FC" />
              <polygon points="392,1180 398,1172 404,1180 398,1188" fill="#FFFFFF" />
              <polygon points="702,1440 708,1432 714,1440 708,1448" fill="#FBCFE8" />
            </g>

            <g className={styles.riverPulseNodes}>
              <circle cx="640" cy="320" r="14" fill="#A5F3FC" opacity="0.55" />
              <circle cx="955" cy="675" r="16" fill="#F9A8D4" opacity="0.55" />
              <circle cx="375" cy="1065" r="16" fill="#C4B5FD" opacity="0.6" />
            </g>

            {/* End-of-Road Luminous Portal Glow (Aligned Centered at x=720) */}
            <ellipse cx="720" cy="1475" rx="340" ry="120" fill="url(#riverEndNexusGlow)" />

            {/* Valley Low-Poly Hills & Glowing Crystal Pyramids */}
            <polygon points="0,120 310,275 160,480 0,410" fill="#4C2E8E" opacity="0.72" stroke="rgba(165,243,252,0.16)" strokeWidth="1" />
            <polygon points="0,410 160,480 90,560 0,540" fill="#3A2373" opacity="0.8" />
            <polygon points="1440,210 1110,335 1265,575 1440,510" fill="#3B2178" opacity="0.78" stroke="rgba(165,243,252,0.16)" strokeWidth="1" />
            <polygon points="1440,510 1265,575 1360,660 1440,640" fill="#2E1A66" opacity="0.82" />
            <polygon points="0,980 280,1140 140,1410 0,1320" fill="#2E1B69" opacity="0.82" stroke="rgba(249,168,212,0.18)" strokeWidth="1" />
            <polygon points="1440,1040 1120,1210 1280,1480 1440,1390" fill="#261559" opacity="0.85" stroke="rgba(249,168,212,0.18)" strokeWidth="1" />
            <polygon points="0,700 150,760 80,860 0,840" fill="#341F70" opacity="0.7" />
            <polygon points="1440,820 1300,880 1380,980 1440,960" fill="#341F70" opacity="0.7" />

            {/* River Bank Boulders */}
            <polygon points="500,290 528,272 548,294 524,312" fill="#3B2A7A" stroke="rgba(165,243,252,0.22)" strokeWidth="0.8" />
            <polygon points="770,356 800,340 818,366 790,380" fill="#45318A" stroke="rgba(249,168,212,0.22)" strokeWidth="0.8" />
            <polygon points="820,640 846,626 862,650 836,662" fill="#3B2A7A" stroke="rgba(165,243,252,0.22)" strokeWidth="0.8" />
            <polygon points="1080,700 1110,684 1126,712 1096,724" fill="#45318A" stroke="rgba(249,168,212,0.22)" strokeWidth="0.8" />
            <polygon points="230,1040 260,1022 278,1048 250,1062" fill="#3B2A7A" stroke="rgba(165,243,252,0.22)" strokeWidth="0.8" />
            <polygon points="508,1100 536,1086 552,1112 524,1124" fill="#45318A" stroke="rgba(249,168,212,0.22)" strokeWidth="0.8" />
            <polygon points="586,1390 612,1376 628,1400 602,1412" fill="#3B2A7A" stroke="rgba(165,243,252,0.22)" strokeWidth="0.8" />
            <polygon points="838,1400 866,1386 882,1410 854,1422" fill="#45318A" stroke="rgba(249,168,212,0.22)" strokeWidth="0.8" />

            {/* Riverside Lanterns marking each pipeline bend */}
            <g className={styles.lanternBlink}>
              <circle cx="520" cy="250" r="22" fill="url(#lanternGlow)" />
              <circle cx="520" cy="250" r="4" fill="#FDE68A" />
              <circle cx="1090" cy="650" r="22" fill="url(#lanternGlow)" />
              <circle cx="1090" cy="650" r="4" fill="#FDE68A" />
              <circle cx="250" cy="1000" r="22" fill="url(#lanternGlow)" />
              <circle cx="250" cy="1000" r="4" fill="#FDE68A" />
            </g>
            <g className={styles.lanternBlinkAlt}>
              <circle cx="790" cy="320" r="22" fill="url(#lanternGlow)" />
              <circle cx="790" cy="320" r="4" fill="#FDE68A" />
              <circle cx="830" cy="700" r="22" fill="url(#lanternGlow)" />
              <circle cx="830" cy="700" r="4" fill="#FDE68A" />
              <circle cx="530" cy="1060" r="22" fill="url(#lanternGlow)" />
              <circle cx="530" cy="1060" r="4" fill="#FDE68A" />
            </g>

            {/* Multi-Faceted Glowing Crystal Obelisks & Pyramids */}
            <g className={styles.crystalBeacon}>
              <polygon points="755,195 805,120 855,195 805,218" fill="#A5F3FC" opacity="0.88" stroke="#FFFFFF" strokeWidth="0.9" />
              <polygon points="805,120 855,195 805,218" fill="#38BDF8" opacity="0.7" />
              <polygon points="215,355 272,272 328,430 215,446" fill="#818CF8" opacity="0.9" stroke="rgba(165,243,252,0.45)" strokeWidth="1" />
              <polygon points="272,272 328,430 272,420" fill="#C4B5FD" opacity="0.55" />
              <polygon points="762,845 818,722 882,845 820,958" fill="#F472B6" opacity="0.84" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
              <polygon points="818,722 882,845 820,860" fill="#F9A8D4" opacity="0.6" />
              <polygon points="1185,1085 1244,965 1304,1085 1244,1135" fill="#67E8F9" opacity="0.84" stroke="rgba(255,255,255,0.4)" strokeWidth="1" />
              <polygon points="120,1250 150,1190 180,1250 150,1272" fill="#C4B5FD" opacity="0.82" stroke="rgba(255,255,255,0.35)" strokeWidth="1" />
              <polygon points="1300,420 1324,372 1348,420 1324,438" fill="#F9A8D4" opacity="0.8" stroke="rgba(255,255,255,0.35)" strokeWidth="1" />
            </g>

            {/* Hovering Survey Drones */}
            <g className={styles.podHoverA}>
              <polygon points="1130,820 1156,812 1182,820 1156,827" fill="#E0E7FF" />
              <ellipse cx="1156" cy="820" rx="18" ry="4.5" fill="#818CF8" />
              <polygon points="1148,825 1152,833 1156,825" fill="#A5F3FC" opacity="0.85" />
              <polygon points="1158,825 1162,833 1166,825" fill="#A5F3FC" opacity="0.85" />
            </g>
            <g className={styles.podHoverB}>
              <polygon points="240,600 264,592 288,600 264,607" fill="#DDD6FE" />
              <ellipse cx="264" cy="600" rx="17" ry="4.2" fill="#C084FC" />
              <polygon points="256,605 260,613 264,605" fill="#F9A8D4" opacity="0.85" />
              <polygon points="266,605 270,613 274,605" fill="#F9A8D4" opacity="0.85" />
            </g>

            {/* Dark-Teal Valley Pine Clusters */}
            <polygon points="445,275 462,192 480,275" fill="#0F766E" />
            <polygon points="482,286 498,188 516,286" fill="#14B8A6" />
            <polygon points="1080,585 1102,472 1124,585" fill="#0F766E" />
            <polygon points="1132,598 1156,462 1180,598" fill="#0D9488" />
            <polygon points="1186,604 1204,520 1222,604" fill="#14B8A6" />
            <polygon points="94,1065 118,935 142,1065" fill="#0F766E" />
            <polygon points="146,1072 164,980 182,1072" fill="#14B8A6" />
            <polygon points="1038,1315 1062,1195 1086,1315" fill="#0D9488" />
            <polygon points="1090,1322 1108,1236 1126,1322" fill="#0F766E" />
            <polygon points="60,620 78,548 96,620" fill="#0D9488" />
            <polygon points="1370,1180 1390,1094 1410,1180" fill="#0F766E" />

            {/* Valley Fireflies */}
            <g className={styles.fireflyDrift}>
              <circle cx="380" cy="420" r="2" fill="#FDE68A" />
              <circle cx="1180" cy="760" r="2.2" fill="#A5F3FC" />
              <circle cx="300" cy="880" r="1.8" fill="#F9A8D4" />
              <circle cx="1000" cy="1180" r="2" fill="#FDE68A" />
              <circle cx="460" cy="1260" r="2" fill="#A5F3FC" />
              <circle cx="980" cy="420" r="1.8" fill="#F9A8D4" />
            </g>
          </svg>

          {/* Section Header (Pipeline Overview) */}
          <div className={`${styles.valleyHeader} ${styles.revealBlock}`} data-reveal>
            <span className={styles.eyebrowCaption}>{t("QUY TRÌNH 6 TẦNG", "6-LAYER PIPELINE")}</span>
            <h2 className={styles.slantedSectionTitle}>
              {t("TỪ DỮ LIỆU THÔ ĐẾN QUYẾT ĐỊNH", "FROM RAW DATA TO DECISION")}
            </h2>
            <p className={styles.valleyHeaderBody}>
              {t(
                "Dòng dữ liệu chảy qua 6 tầng xử lý: từ giá EOD chuẩn mốc thời gian, chuẩn hóa IAS 33, mô hình đa nhân tố, tín hiệu VN100, AI đối soát bằng chứng cho đến đo lường rủi ro danh mục.",
                "Data flows through six processing layers: Point-in-Time EOD prices, IAS 33 normalization, multi-factor models, VN100 signals, evidence-audited AI, and portfolio risk measurement."
              )}
            </p>
          </div>

          {/* Staggered Roadmap Cards 06..01 with Hologram Projector Orbs */}
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
                        <span className={styles.milestoneTitle}>{card.title}</span>
                      </div>
                      <ul className={styles.milestoneList}>
                        {card.bullets.map((bullet, bIdx) => (
                          <li key={bIdx} className={styles.milestoneItem}>
                            <span className={styles.milestoneArrow} aria-hidden="true">
                              ↗
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
                    <div className={styles.hologramCone} aria-hidden="true" />
                    <div className={styles.pearlOrb} aria-hidden="true" />
                  </div>
                </div>
              );
            })}
          </div>

          {/* Harmonious End-of-Road Connect Portal Where Winding River Terminates */}
          <div className={`${styles.roadEndPortal} ${styles.revealBlock}`} data-reveal>
            <div className={styles.portalNexusRing} aria-hidden="true">
              <span className={styles.portalRingOuter} />
              <span className={styles.portalRingInner} />
              <span className={styles.portalGem} />
            </div>
            <span className={styles.eyebrowCaption}>
              {t("HOÀN TẤT QUY TRÌNH · SẴN SÀNG TRUY CẬP", "END OF PIPELINE · READY TO ENTER")}
            </span>
            <h2 className={styles.portalHeading}>
              {t("KHỞI CHẠY TRẠM PHÂN TÍCH", "INITIALIZE WORKSTATION")}
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
                className={styles.pinkChamferBtn}
                onClick={() => triggerBreach()}
              >
                {t("KẾT NỐI TRẠM PHÂN TÍCH →", "CONNECT WORKSTATION →")}
              </button>
              <button
                type="button"
                className={styles.whiteRectBtn}
                onClick={() => triggerBreach("/ai")}
              >
                {t("MỞ TRỢ LÝ AI", "OPEN AI ANALYST")}
              </button>
            </div>
            <span className={styles.portalFootHint}>
              {t(
                "Nhấn Kết nối hoặc phím ESC để bước vào Bảng điều khiển",
                "Click CONNECT or press ESC to enter the Dashboard"
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
