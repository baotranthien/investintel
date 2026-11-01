/**
 * Context handoff utilities for Opportunities -> AI Analyst navigation.
 */

/**
 * Normalizes and validates a stock ticker symbol.
 * Standard convention: 2-10 alphanumeric characters (e.g. FPT, HPG, VCB, VN30, FUEVN100).
 * Rejects non-alphanumeric, whitespace, or excessively long strings.
 */
export function normalizeTicker(rawTicker: string | null | undefined): string | null {
  if (!rawTicker) return null;
  const trimmed = rawTicker.trim().toUpperCase();
  if (!/^[A-Z0-9]{2,10}$/.test(trimmed)) {
    return null;
  }
  return trimmed;
}

/**
 * Builds the standardized Vietnamese analytical question for a given stock opportunity.
 * Format:
 * "Phân tích cơ hội đầu tư của cổ phiếu {SYMBOL} dựa trên dữ liệu hiện có trong InvestIntel. Hãy trình bày các luận điểm hỗ trợ, định giá, rủi ro, độ mới của dữ liệu và những thông tin chưa đủ bằng chứng. Phân biệt số liệu thực tế với ước tính."
 */
export function buildOpportunityQuestion(symbol: string): string {
  const clean = normalizeTicker(symbol) || symbol.trim().toUpperCase();
  return `Phân tích cơ hội đầu tư của cổ phiếu ${clean} dựa trên dữ liệu hiện có trong InvestIntel. Hãy trình bày các luận điểm hỗ trợ, định giá, rủi ro, độ mới của dữ liệu và những thông tin chưa đủ bằng chứng. Phân biệt số liệu thực tế với ước tính.`;
}

/**
 * Builds the URL with properly encoded query parameters for navigating from Opportunities to AI Analyst.
 */
export function buildOpportunityAIUrl(symbol: string): string {
  const clean = normalizeTicker(symbol) || symbol.trim().toUpperCase();
  const question = buildOpportunityQuestion(clean);
  const params = new URLSearchParams({
    symbol: clean,
    source: "opportunities",
    q: question,
  });
  return `/ai?${params.toString()}`;
}

