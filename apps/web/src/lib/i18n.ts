"use client";

import { useCallback, useSyncExternalStore } from "react";

export type AppLocale = "vi" | "en";

export const LOCALE_STORAGE_KEY = "investintel:locale:v1";
export const LOCALE_CHANGE_EVENT = "investintel:locale-change";

export function getLocalePreference(): AppLocale {
  if (typeof window === "undefined") return "vi";
  try {
    const stored = window.localStorage.getItem(LOCALE_STORAGE_KEY);
    if (stored === "en" || stored === "vi") {
      return stored;
    }
  } catch {
    // LocalStorage may be unavailable
  }
  return "vi";
}

export function applyLocaleToDocument(locale: AppLocale): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.setAttribute("data-locale", locale);
  root.lang = locale;

  if (
    document.title === "InvestIntel | Đầu tư có bằng chứng" ||
    document.title === "InvestIntel | Evidence-Backed Investing"
  ) {
    document.title =
      locale === "en"
        ? "InvestIntel | Evidence-Backed Investing"
        : "InvestIntel | Đầu tư có bằng chứng";
  }
}

export function setLocalePreference(locale: AppLocale): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    // Ignore storage errors
  }

  applyLocaleToDocument(locale);
  window.dispatchEvent(
    new CustomEvent<{ locale: AppLocale }>(LOCALE_CHANGE_EVENT, {
      detail: { locale },
    })
  );
}

export function pickLocaleText(locale: AppLocale, vi: string, en: string): string {
  return locale === "en" ? en : vi;
}

function subscribeLocale(callback: () => void): () => void {
  if (typeof window === "undefined") return () => {};

  const handleCustomChange = () => callback();
  const handleStorage = (e: StorageEvent) => {
    if (e.key === LOCALE_STORAGE_KEY || e.key === null) {
      applyLocaleToDocument(getLocalePreference());
      callback();
    }
  };

  window.addEventListener(LOCALE_CHANGE_EVENT, handleCustomChange);
  window.addEventListener("storage", handleStorage);
  return () => {
    window.removeEventListener(LOCALE_CHANGE_EVENT, handleCustomChange);
    window.removeEventListener("storage", handleStorage);
  };
}

function getClientLocaleSnapshot(): AppLocale {
  return getLocalePreference();
}

function getServerLocaleSnapshot(): AppLocale {
  return "vi";
}

function subscribeMounted(): () => void {
  return () => {};
}

function getClientMounted(): boolean {
  return true;
}

function getServerMounted(): boolean {
  return false;
}

export function useLocale() {
  const locale = useSyncExternalStore(
    subscribeLocale,
    getClientLocaleSnapshot,
    getServerLocaleSnapshot
  );
  const mounted = useSyncExternalStore(
    subscribeMounted,
    getClientMounted,
    getServerMounted
  );

  const setLocale = useCallback((next: AppLocale) => {
    setLocalePreference(next);
  }, []);

  const toggleLocale = useCallback(() => {
    const next: AppLocale = getLocalePreference() === "en" ? "vi" : "en";
    setLocalePreference(next);
  }, []);

  const t = useCallback(
    (vi: string, en: string): string => (locale === "en" ? en : vi),
    [locale]
  );

  return {
    locale,
    isEn: locale === "en",
    setLocale,
    toggleLocale,
    t,
    mounted,
  };
}

export function translateQuantEnum(
  value: string | null | undefined,
  locale: AppLocale
): string {
  if (!value) return locale === "en" ? "N/A" : "Chưa xác định";
  const trimmed = value.trim();
  const suffixMatch = trimmed.match(/^(.*?)(\s*\([^)]+\))$/);
  const baseRaw = suffixMatch ? suffixMatch[1].trim() : trimmed;
  const suffix = suffixMatch ? suffixMatch[2] : "";
  const key = baseRaw.toUpperCase().replace(/\s+/g, "_");
  const map: Record<string, { vi: string; en: string }> = {
    BULLISH: { vi: "Tích cực (Rủi ro ưa thích)", en: "Bullish (Risk-On)" },
    NEUTRAL: { vi: "Trung tính (Cân bằng)", en: "Neutral (Balanced)" },
    BEARISH: { vi: "Thận trọng (Phòng thủ)", en: "Bearish (Risk-Off)" },
    RISK_ON: { vi: "Ưa thích rủi ro", en: "Risk-On" },
    RISK_OFF: { vi: "Phòng thủ rủi ro", en: "Risk-Off" },
    UNDERVALUED: { vi: "Định giá hấp dẫn", en: "Undervalued" },
    FAIR: { vi: "Định giá hợp lý", en: "Fair Value" },
    FAIR_VALUE: { vi: "Định giá hợp lý", en: "Fair Value" },
    OVERVALUED: { vi: "Định giá cao", en: "Overvalued" },
    STRONG_BUY: { vi: "Khả quan nổi bật", en: "Strong Outperform" },
    BUY: { vi: "Tích cực", en: "Outperform" },
    HOLD: { vi: "Trung lập", en: "Neutral" },
    SELL: { vi: "Kém khả quan", en: "Underperform" },
    HIGH: { vi: "Cao", en: "High" },
    CAO: { vi: "Cao", en: "High" },
    MEDIUM: { vi: "Trung bình", en: "Medium" },
    MODERATE: { vi: "Trung bình", en: "Moderate" },
    TRUNG_BÌNH: { vi: "Trung bình", en: "Medium" },
    LOW: { vi: "Thấp", en: "Low" },
    THẤP: { vi: "Thấp", en: "Low" },
    SHORT_TERM: { vi: "Ngắn hạn (T+5 — T+20)", en: "Short-Term (5–20D)" },
    MEDIUM_TERM: { vi: "Trung hạn (3–6 tháng)", en: "Medium-Term (3–6M)" },
    LONG_TERM: { vi: "Dài hạn (1–3 năm)", en: "Long-Term (1–3Y)" },
  };
  const found = map[key];
  if (found) {
    return `${locale === "en" ? found.en : found.vi}${suffix}`;
  }
  return trimmed.replace(/_/g, " ");
}

export function translateSectorName(
  sector: string | null | undefined,
  locale: AppLocale
): string {
  if (!sector) return "VN100";
  const key = sector.trim().toUpperCase().replace(/\s+/g, "_");
  const map: Record<string, { vi: string; en: string }> = {
    BANK: { vi: "Ngân hàng", en: "Banking" },
    BANKING: { vi: "Ngân hàng", en: "Banking" },
    REAL_ESTATE: { vi: "Bất động sản", en: "Real Estate" },
    MATERIALS: { vi: "Vật liệu", en: "Materials" },
    RETAIL: { vi: "Bán lẻ", en: "Retail" },
    TECHNOLOGY: { vi: "Công nghệ", en: "Technology" },
    OIL_GAS: { vi: "Dầu khí", en: "Oil & Gas" },
    SECURITIES: { vi: "Chứng khoán", en: "Securities" },
    FINANCIALS: { vi: "Tài chính", en: "Financials" },
    CONSUMER: { vi: "Tiêu dùng", en: "Consumer" },
    CONSUMER_STAPLES: { vi: "Tiêu dùng thiết yếu", en: "Consumer Staples" },
    UTILITIES: { vi: "Tiện ích", en: "Utilities" },
    INDUSTRIALS: { vi: "Công nghiệp", en: "Industrials" },
    HEALTHCARE: { vi: "Y tế & Dược", en: "Healthcare" },
    TRANSPORTATION: { vi: "Vận tải & Logistics", en: "Transportation" },
    INSURANCE: { vi: "Bảo hiểm", en: "Insurance" },
    TELECOM: { vi: "Viễn thông", en: "Telecom" },
    KHÁC: { vi: "Đa ngành", en: "Diversified" },
  };
  const hit = map[key];
  if (hit) return locale === "en" ? hit.en : hit.vi;
  return sector.replace(/_/g, " ");
}

export function translateOpportunityDriver(
  text: string | null | undefined,
  locale: AppLocale
): string {
  if (!text) return "";
  if (locale !== "en") return text;

  const rules: Array<[RegExp, string]> = [
    [/Định giá hấp dẫn so với cơ sở\s*\(điểm:\s*([^)]+)\)\.?/i, "Attractive valuation vs. base case (score: $1)."],
    [/Định giá hợp lý so với cơ sở\s*\(điểm:\s*([^)]+)\)\.?/i, "Fair valuation vs. base case (score: $1)."],
    [/Định giá cao so với cơ sở\s*\(điểm:\s*([^)]+)\)\.?/i, "Elevated valuation vs. base case (score: $1)."],
    [/Định giá đắt so với cơ sở\s*\(điểm:\s*([^)]+)\)\.?/i, "Expensive valuation vs. base case (score: $1)."],
    [/Nền tảng doanh nghiệp mạnh\s*\(điểm:\s*([^)]+)\)\.?/i, "Strong corporate fundamentals (score: $1)."],
    [/Nền tảng cơ bản ổn định\s*\(điểm:\s*([^)]+)\)\.?/i, "Solid fundamental base (score: $1)."],
    [/Xung lượng dòng tiền tích cực\s*\(điểm:\s*([^)]+)\)\.?/i, "Positive momentum regime (score: $1)."],
    [/Rủi ro biến động thấp\s*\(điểm:\s*([^)]+)\)\.?/i, "Low volatility risk profile (score: $1)."],
  ];

  let out = text;
  for (const [pattern, replacement] of rules) {
    out = out.replace(pattern, replacement);
  }
  return out;
}

export function translateResearchCopy(
  text: string | null | undefined,
  locale: AppLocale
): string {
  if (!text) return "";
  if (locale !== "en") return text;

  let out = translateOpportunityDriver(text, locale);
  out = out.replace(/ngành\s+Khác\b/gi, "ngành Diversified");
  const rules: Array<[RegExp, string]> = [
    [
      /Doanh nghiệp tiềm năng ngành\s+([^,]+),\s*duy trì hiệu quả hoạt động và đà tăng trưởng bền vững\.?/i,
      "Growth-oriented $1 enterprise maintaining operational discipline and sustainable expansion.",
    ],
    [
      /Doanh nghiệp đầu ngành\s+([^,]+),\s*ROE đạt\s*([^,]+),\s*tăng trưởng LNST\s*([^,]+)\s*YoY,\s*định giá P\/E\s*([^,]+),\s*đòn bẩy D\/E an toàn\s*\(([^)]+)\)\.?/i,
      "Sector-leading $1 franchise: ROE $2, net income growth $3 YoY, P/E $4, conservative leverage (D/E $5).",
    ],
    [
      /Hiệu quả sinh lời cổ đông xuất sắc với ROE đạt\s*([^,]+),\s*vượt trội so với trung vị ngành\s*([^.]+)\.?/i,
      "Superior shareholder return with ROE at $1, outperforming the $2 sector median.",
    ],
    [
      /Lợi nhuận sau thuế đạt\s*([^Y]+)YoY,\s*tăng trưởng bứt phá\.?/i,
      "Net profit growth reached $1 YoY, demonstrating breakout earnings momentum.",
    ],
    [
      /Lợi nhuận sau thuế đạt\s*([^Y]+)YoY,\s*đang hồi phục theo chu kỳ\.?/i,
      "Net profit growth stood at $1 YoY, undergoing a cyclical earnings recovery.",
    ],
    [
      /Doanh thu tăng trưởng\s*([^Y]+)YoY nhờ mở rộng thị phần và năng lực triển khai dự án\.?/i,
      "Revenue grew $1 YoY driven by market-share expansion and execution capacity.",
    ],
    [
      /Biên lợi nhuận ròng duy trì ổn định ở mức\s*([^,]+),\s*quản trị chi phí hoạt động tốt\.?/i,
      "Net profit margin held steady at $1 with disciplined operating cost control.",
    ],
    [
      /Định giá P\/E ở mức\s*([^\s]+)\s*nằm trong vùng định giá hấp dẫn so với tiềm năng tăng trưởng trung hạn\.?/i,
      "P/E multiple of $1 sits in an attractive valuation zone relative to medium-term growth.",
    ],
    [
      /Rủi ro thị trường:\s*Biến động giá chịu tác động từ xu hướng chung của VN-Index\s*\(Điểm rủi ro thị trường:\s*([^)]+)\)\.?/i,
      "Market risk: Price action remains sensitive to broad VN-Index regime shifts (Market risk score: $1).",
    ],
    [
      /Cơ cấu tài chính:\s*Tỷ lệ nợ\/vốn chủ D\/E đạt\s*([^\s(]+)\s*\(an toàn,\s*áp lực nợ vay thấp\)\.?/i,
      "Capital structure: Debt-to-Equity ratio at $1 (conservative leverage, low debt service pressure).",
    ],
    [
      /Cơ cấu tài chính:\s*Tỷ lệ nợ\/vốn chủ D\/E đạt\s*([^\s(]+)\s*\(đòn bẩy trung bình\)\.?/i,
      "Capital structure: Debt-to-Equity ratio at $1 (moderate financial leverage).",
    ],
    [
      /Cơ cấu tài chính:\s*Tỷ lệ nợ\/vốn chủ D\/E đạt\s*([^\s(]+)\s*\(([^)]+)\)\.?/i,
      "Capital structure: Debt-to-Equity ratio at $1 ($2).",
    ],
    [
      /Biên an toàn định giá đạt\s*([^\s]+)\s*so với giá trị nội tại ước tính\s*\(([^)]+)\)\.?/i,
      "Valuation margin of safety stands at $1 relative to estimated intrinsic value ($2).",
    ],
    [
      /Rủi ro định giá:\s*Thị giá hiện tại cao hơn giá trị hợp lý ước tính\s*\(Biên an toàn\s*([^)]+)\),\s*cần kiên nhẫn chờ nhịp điều chỉnh giá\.?/i,
      "Valuation risk: Market price trades above estimated fair value (Margin of Safety $1); wait for a pullback.",
    ],
    [
      /Rủi ro vĩ mô:\s*Biến động tỷ giá USD\/VND và chu kỳ kinh tế chung có thể tác động đến tốc độ tăng trưởng ngắn hạn\.?/i,
      "Macro risk: USD/VND FX volatility and broader macro cycles may weigh on near-term growth.",
    ],
    [
      /ROE suy giảm xuống dưới\s*([^\s]+)\s*hoặc tăng trưởng LNST âm 2 quý liên tiếp/i,
      "ROE declines below $1 or net profit growth turns negative for 2 consecutive quarters",
    ],
    [
      /Tỷ lệ (?:nợ|nợ\/vốn chủ|đòn bẩy) D\/E vượt quá\s*([^\s.;]+)\s*hoặc biên an toàn định giá âm quá\s*([^\s.;]+)/i,
      "Debt-to-Equity D/E exceeds $1 or valuation margin of safety falls below $2",
    ],
    [
      /Tỷ lệ (?:nợ|nợ\/vốn chủ|đòn bẩy) D\/E vượt quá\s*([^\s.;]+)/i,
      "Debt-to-Equity D/E exceeds $1",
    ],
    [
      /hoặc biên an toàn định giá âm quá\s*([^\s.;]+)/i,
      "or valuation margin of safety falls below $1",
    ],
    [
      /biên lợi nhuận ròng sụt giảm trên\s*([^\s]+)\s*so với cùng kỳ/i,
      "net margin compresses by more than $1 YoY",
    ],
  ];

  for (const [pattern, replacement] of rules) {
    out = out.replace(pattern, replacement);
  }
  out = out.replace(/the\s+([A-Z_]+)\s+sector\s+median/g, (_m, sec: string) => `the ${translateSectorName(sec, "en")} sector median`);
  return out;
}
