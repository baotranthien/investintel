# INVESTINTEL — INTERACTIVE CONTROLS ACCEPTANCE MATRIX
**Date:** 2026-11-02 | **Branch:** `phase6-local-stability` | **Test Environment:** Headless Chrome Playwright

| Page | Control / Action Name | Advertised Action | Actual Action Verified | API Endpoint | Result | Screenshot Evidence |
|---|---|---|---|---|:---:|---|
| Dashboard (/) | Làm mới trạng thái | Refreshes provider and asset state | Clicked reload, API re-fetched successfully | `GET /api/v1/data/providers` | **PASS** | `screenshots/dashboard_reloaded.png` |
| Screener (/screener) | Bộ lọc ROE tối thiểu | Filters stocks with ROE >= 15% | Filled 15 and submitted, filtered results rendered | `GET /api/v1/screener?roe_min=15` | **PASS** | `screenshots/ctrl_screener_filtered.png` |
| Screener (/screener) | Đặt lại (Reset) | Clears all filter inputs to defaults | Clicked reset, inputs cleared and default universe restored | `GET /api/v1/screener` | **PASS** | `screenshots/ctrl_screener_reset.png` |
| Opportunities (/opportunities) | Thẻ lọc ngành Ngân hàng | Filters opportunities by Banking sector | Clicked Ngân hàng, results filtered to banking assets | `GET /api/v1/opportunity/scanner?sector=Banking` | **PASS** | `screenshots/ctrl_opp_chip.png` |
| Valuation (/valuation) | Chọn mã cổ phiếu (Dropdown) | Changes active stock for DCF & multiple valuation | Selected VCB, valuation metrics reloaded for VCB | `GET /api/v1/valuation/VCB` | **PASS** | `screenshots/ctrl_valuation_vcb.png` |
| Research (/research) | Chuyển tab Chiến lược Backtest | Switches view to quantitative backtesting configuration | Clicked Backtest tab, strategy parameter form rendered | `Client Tab Navigation` | **PASS** | `screenshots/ctrl_research_backtest_tab.png` |
| AI Analyst (/ai) | Thẻ gợi ý câu hỏi nhanh | Prefills query textarea with market question | Clicked prompt chip, query prefilled in textarea | `DOM Form Prefill` | **PASS** | `screenshots/ctrl_ai_chip_prefill.png` |
