from datetime import date
from typing import Any, Optional

from sqlalchemy.orm import Session

from database.connection import SessionLocal
from database.models import (
    Asset, AssetDecisionSnapshot, WatchlistItem,
    BankMetric, MacroCommodity, Price
)
from services.decision.engine import build_decision_context
from services.events.engine import EventEngine
from services.macro.observations import get_latest_macro_series
from services.market.dashboard import build_market_dashboard
from services.portfolio.engine import portfolio_dashboard, portfolio_fit
from services.research.rag import DocumentRAGService


TOOL_NAMES = (
    "asset",
    "fundamentals",
    "valuation",
    "factors",
    "risk",
    "macro",
    "regime",
    "events",
    "opportunity",
    "portfolio",
    "watchlist",
    "historical_snapshot",
    "evidence",
    "document_retrieval",
)


def _status(data: Any) -> str:
    if data is None:
        return "INSUFFICIENT_DATA"
    if isinstance(data, dict):
        status = data.get("status")
        if isinstance(status, str):
            return status
        return "AVAILABLE" if data else "INSUFFICIENT_DATA"
    if isinstance(data, list):
        return "AVAILABLE" if data else "INSUFFICIENT_DATA"
    return "AVAILABLE"


def _get_bank_evidence(db: Session, asset: Asset, as_of: date) -> list[dict[str, Any]]:
    is_bank = (asset.sector and "BANK" in asset.sector.upper()) or asset.symbol in {
        "VCB", "MBB", "TCB", "BID", "CTG", "ACB", "VPB", "STB", "HDB", "TPB", "MSB", "SHB", "VIB", "LPB", "SSB", "EIB", "OCB"
    }
    if not is_bank:
        return []

    metrics = (
        db.query(BankMetric)
        .filter(BankMetric.asset_id == asset.id, BankMetric.fiscal_date <= as_of)
        .order_by(BankMetric.fiscal_date.desc())
        .limit(2)
        .all()
    )
    evidence: list[dict[str, Any]] = []
    for m in metrics:
        p_str = m.fiscal_period or str(m.fiscal_date)
        items = [
            ("nim", m.nim, "%", f"Biên lãi ròng (NIM) {asset.symbol} kỳ {p_str}: {m.nim}%"),
            ("casa_ratio", m.casa_ratio, "%", f"Tỷ lệ tiền gửi không kỳ hạn (CASA) {asset.symbol} kỳ {p_str}: {m.casa_ratio}%"),
            ("credit_growth", m.credit_growth, "%", f"Tăng trưởng tín dụng {asset.symbol} kỳ {p_str}: {m.credit_growth}%"),
            ("npl_ratio", m.npl_ratio, "%", f"Tỷ lệ nợ xấu (NPL) {asset.symbol} kỳ {p_str}: {m.npl_ratio}%"),
            ("llr_ratio", m.llr_ratio, "%", f"Tỷ lệ bao phủ nợ xấu (LLR) {asset.symbol} kỳ {p_str}: {m.llr_ratio}%"),
        ]
        for metric_name, val, unit, note in items:
            if val is not None:
                evidence.append({
                    "claim_type": "FACT",
                    "responsible_module": "bank_metrics",
                    "metric": metric_name,
                    "symbol": asset.symbol,
                    "value": val,
                    "unit": unit,
                    "source": m.source or "BCTC_NGAN_HANG",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": m.fiscal_date.isoformat(),
                    "note": note,
                })
    return evidence


def _get_commodity_evidence_and_series(
    db: Session,
    norm_symbols: list[str],
    as_of: date,
    question: Optional[str] = None,
) -> tuple[list[dict[str, Any]], list[float] | None, list[float] | None]:
    evidence: list[dict[str, Any]] = []
    c_series: list[float] | None = None
    s_series: list[float] | None = None

    energy_symbols = {"PLX", "GAS", "PVD", "PVS", "BSR", "OIL"}
    has_energy_sym = any(s in energy_symbols for s in norm_symbols)
    q_str = (question or "").lower()
    has_oil_keyword = any(k in q_str for k in ("dầu", "dau", "brent", "wti", "oil", "nhiên liệu"))

    if has_energy_sym or has_oil_keyword:
        latest_brent = (
            db.query(MacroCommodity)
            .filter(MacroCommodity.commodity_code == "BRENT", MacroCommodity.observation_date <= as_of)
            .order_by(MacroCommodity.observation_date.desc())
            .first()
        )
        if latest_brent:
            chg_str = f" ({latest_brent.change_pct:+.2f}%)" if latest_brent.change_pct is not None else ""
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "macro",
                "metric": "brent_close",
                "symbol": "BRENT",
                "value": latest_brent.close_price,
                "unit": latest_brent.unit or "USD/barrel",
                "source": latest_brent.source or "PUBLIC_COMMODITY_FEED",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": latest_brent.observation_date.isoformat(),
                "note": f"Giá dầu Brent giao ngay tại ngày {latest_brent.observation_date}: {latest_brent.close_price} USD/thùng{chg_str}.",
            })

        # Calculate time series correlation if energy stock present
        target_sym = next((s for s in norm_symbols if s in energy_symbols), None)
        if target_sym:
            target_asset = db.query(Asset).filter(Asset.symbol == target_sym).first()
            if target_asset:
                # 1. Stock price vs Brent spot price series
                stock_prices = (
                    db.query(Price.observation_date, Price.raw_close)
                    .filter(Price.asset_id == target_asset.id, Price.observation_date <= as_of)
                    .order_by(Price.observation_date.asc())
                    .all()
                )
                brent_prices = (
                    db.query(MacroCommodity.observation_date, MacroCommodity.close_price)
                    .filter(MacroCommodity.commodity_code == "BRENT", MacroCommodity.observation_date <= as_of)
                    .order_by(MacroCommodity.observation_date.asc())
                    .all()
                )
                brent_map = {d: p for d, p in brent_prices}
                paired_s = []
                paired_c = []
                for d, sp in stock_prices:
                    if d in brent_map:
                        paired_s.append(sp)
                        paired_c.append(brent_map[d])
                if len(paired_s) >= 5:
                    s_series = paired_s
                    c_series = paired_c

                # 2. Corporate Quarterly Revenue vs Quarterly Average Brent Price (Q7 requirement)
                from database.models import FinancialStatement, NormalizedIncome
                import math
                stmts = (
                    db.query(FinancialStatement, NormalizedIncome)
                    .join(NormalizedIncome, NormalizedIncome.statement_id == FinancialStatement.id)
                    .filter(
                        FinancialStatement.asset_id == target_asset.id,
                        FinancialStatement.period_type == "QUARTERLY",
                        FinancialStatement.fiscal_period_end <= as_of,
                        NormalizedIncome.revenue.isnot(None),
                        NormalizedIncome.revenue > 0,
                    )
                    .order_by(FinancialStatement.fiscal_period_end.asc())
                    .all()
                )
                rev_by_quarter: dict[date, dict[str, Any]] = {}
                for fs, inc in stmts:
                    d = fs.fiscal_period_end
                    if d not in rev_by_quarter or fs.consolidation == "CONSOLIDATED":
                        rev_by_quarter[d] = {
                            "year": fs.fiscal_year,
                            "quarter": fs.fiscal_quarter,
                            "start": fs.fiscal_period_start,
                            "end": fs.fiscal_period_end,
                            "revenue": float(inc.revenue),
                        }

                aligned_revs: list[float] = []
                aligned_brents: list[float] = []
                periods_list: list[str] = []
                for d, q_info in sorted(rev_by_quarter.items()):
                    start = q_info["start"]
                    if not start:
                        m = d.month
                        start = date(d.year, 1 if m <= 3 else (4 if m <= 6 else (7 if m <= 9 else 10)), 1)
                    brent_in_q = [p for obs_d, p in brent_prices if start <= obs_d <= d]
                    if brent_in_q:
                        avg_b = sum(brent_in_q) / len(brent_in_q)
                        aligned_revs.append(q_info["revenue"])
                        aligned_brents.append(avg_b)
                        periods_list.append(f"{q_info['year']}Q{q_info['quarter']}")

                n_samples = len(aligned_revs)
                if n_samples >= 4:
                    mean_x = sum(aligned_revs) / n_samples
                    mean_y = sum(aligned_brents) / n_samples
                    cov = sum((aligned_revs[i] - mean_x) * (aligned_brents[i] - mean_y) for i in range(n_samples))
                    var_x = sum((aligned_revs[i] - mean_x) ** 2 for i in range(n_samples))
                    var_y = sum((aligned_brents[i] - mean_y) ** 2 for i in range(n_samples))
                    denom = math.sqrt(var_x * var_y)
                    rev_corr = round(cov / denom, 4) if denom > 0 else None
                    if rev_corr is not None:
                        period_range_str = f"{periods_list[0]} đến {periods_list[-1]}"
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "macro",
                            "metric": "revenue_commodity_correlation",
                            "symbol": target_sym,
                            "value": rev_corr,
                            "unit": "coefficient",
                            "source": "INVESTINTEL_TIME_SERIES_ALIGNER",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": as_of.isoformat(),
                            "note": f"Hệ số tương quan tuyến tính Pearson giữa doanh thu thuần theo quý của {target_sym} và giá dầu Brent trung bình quý (Levels): {rev_corr:.4f} (mẫu {n_samples} quý, từ {period_range_str}).",
                        })
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "macro",
                            "metric": "revenue_commodity_correlation_levels",
                            "symbol": target_sym,
                            "value": rev_corr,
                            "unit": "coefficient",
                            "source": "INVESTINTEL_TIME_SERIES_ALIGNER",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": as_of.isoformat(),
                            "note": f"Hệ số tương quan chuỗi quy mô tuyệt đối (Raw Levels) giữa doanh thu thuần quý {target_sym} và giá dầu Brent trung bình: {rev_corr:.4f} (N={n_samples}). Lưu ý: Tương quan cấp độ phản ánh xu hướng dài hạn phi dừng, không đồng nghĩa quan hệ nhân quả.",
                        })

                        # QoQ % change correlation
                        qoq_rev = [(aligned_revs[i] - aligned_revs[i-1]) / aligned_revs[i-1] for i in range(1, n_samples)]
                        qoq_brent = [(aligned_brents[i] - aligned_brents[i-1]) / aligned_brents[i-1] for i in range(1, n_samples)]
                        mean_qx = sum(qoq_rev) / len(qoq_rev)
                        mean_qy = sum(qoq_brent) / len(qoq_brent)
                        cov_q = sum((qoq_rev[i] - mean_qx) * (qoq_brent[i] - mean_qy) for i in range(len(qoq_rev)))
                        var_qx = sum((x - mean_qx) ** 2 for x in qoq_rev)
                        var_qy = sum((y - mean_qy) ** 2 for y in qoq_brent)
                        denom_q = math.sqrt(var_qx * var_qy)
                        r_qoq = round(cov_q / denom_q, 4) if denom_q > 0 else None
                        if r_qoq is not None:
                            evidence.append({
                                "claim_type": "MODEL_OUTPUT",
                                "responsible_module": "macro",
                                "metric": "revenue_commodity_correlation_qoq",
                                "symbol": target_sym,
                                "value": r_qoq,
                                "unit": "coefficient",
                                "source": "INVESTINTEL_TIME_SERIES_ALIGNER",
                                "data_origin": "CANONICAL_DATABASE",
                                "freshness": "AVAILABLE",
                                "observation_date": as_of.isoformat(),
                                "note": f"Hệ số tương quan giữa tốc độ tăng trưởng doanh thu quý-trên-quý (QoQ % Change) của {target_sym} và biến động giá dầu Brent quý: {r_qoq:+.4f} (N={len(qoq_rev)} quý). Phản ánh độ co giãn chuyển giá ngắn hạn.",
                            })

                        # YoY % change correlation
                        if n_samples >= 8:
                            yoy_rev = [(aligned_revs[i] - aligned_revs[i-4]) / aligned_revs[i-4] for i in range(4, n_samples)]
                            yoy_brent = [(aligned_brents[i] - aligned_brents[i-4]) / aligned_brents[i-4] for i in range(4, n_samples)]
                            mean_yx = sum(yoy_rev) / len(yoy_rev)
                            mean_yy = sum(yoy_brent) / len(yoy_brent)
                            cov_y = sum((yoy_rev[i] - mean_yx) * (yoy_brent[i] - mean_yy) for i in range(len(yoy_rev)))
                            var_yx = sum((x - mean_yx) ** 2 for x in yoy_rev)
                            var_yy = sum((y - mean_yy) ** 2 for y in yoy_brent)
                            denom_y = math.sqrt(var_yx * var_yy)
                            r_yoy = round(cov_y / denom_y, 4) if denom_y > 0 else None
                            if r_yoy is not None:
                                evidence.append({
                                    "claim_type": "MODEL_OUTPUT",
                                    "responsible_module": "macro",
                                    "metric": "revenue_commodity_correlation_yoy",
                                    "symbol": target_sym,
                                    "value": r_yoy,
                                    "unit": "coefficient",
                                    "source": "INVESTINTEL_TIME_SERIES_ALIGNER",
                                    "data_origin": "CANONICAL_DATABASE",
                                    "freshness": "AVAILABLE",
                                    "observation_date": as_of.isoformat(),
                                    "note": f"Hệ số tương quan giữa tăng trưởng doanh thu cùng kỳ năm trước (YoY % Change) của {target_sym} và biến động giá dầu Brent năm: {r_yoy:+.4f} (N={len(yoy_rev)} quý).",
                                })

    return evidence, c_series, s_series


def _get_valuation_dcf_evidence(db: Session, symbol: str, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL"):
        return evidence
    try:
        from apps.api.routers.valuation import _load_fundamentals_for_valuation, _get_latest_price, _get_asset_sector
        from services.fundamentals.sector_models import get_sector_for_symbol
        from services.valuation.builder import ValuationSnapshotBuilder
        funds = _load_fundamentals_for_valuation(symbol, as_of)
        price = _get_latest_price(symbol, as_of)
        sector = _get_asset_sector(symbol) or get_sector_for_symbol(symbol) or "GENERAL"
        if funds and price:
            builder = ValuationSnapshotBuilder(symbol, sector)
            val_snap = builder.build(funds, price, as_of)
            if val_snap and val_snap.composite_fair_value:
                comp_range = val_snap.composite_fair_value.range
                if comp_range.base and comp_range.base > 0:
                    evidence.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "valuation",
                        "metric": "composite_fair_value_base",
                        "symbol": symbol,
                        "value": round(comp_range.base, 0),
                        "unit": "VND",
                        "source": "VALUATION_SNAPSHOT_BUILDER",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": as_of.isoformat(),
                        "note": f"Giá trị hợp lý tổng hợp kịch bản cơ sở (Composite Base Case) của {symbol}: {comp_range.base:,.0f} VND (Bear: {comp_range.bear:,.0f} VND, Bull: {comp_range.bull:,.0f} VND).",
                    })
                    if val_snap.margin_of_safety is not None:
                        mos_pct = round(val_snap.margin_of_safety * 100, 2)
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "valuation",
                            "metric": "margin_of_safety",
                            "symbol": symbol,
                            "value": mos_pct,
                            "unit": "%",
                            "source": "VALUATION_SNAPSHOT_BUILDER",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": as_of.isoformat(),
                            "note": f"Biên an toàn (Margin of Safety) so với thị giá {price:,.0f} VND: {mos_pct:+.2f}%.",
                        })
            for m in getattr(val_snap, "methods", []):
                if m.method == "DCF" and m.fair_value.base > 0:
                    evidence.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "valuation",
                        "metric": "dcf_base",
                        "symbol": symbol,
                        "value": round(m.fair_value.base, 0),
                        "unit": "VND",
                        "source": "DCF_VALUATION_ENGINE",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": as_of.isoformat(),
                        "note": f"Định giá DCF kịch bản cơ sở (Base Case) của {symbol}: {m.fair_value.base:,.0f} VND/cổ phiếu (Bear: {m.fair_value.bear:,.0f} VND, Bull: {m.fair_value.bull:,.0f} VND).",
                    })
                elif m.method == "Relative P/E" and m.fair_value.base > 0:
                    evidence.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "valuation",
                        "metric": "pe_fair_value",
                        "symbol": symbol,
                        "value": round(m.fair_value.base, 0),
                        "unit": "VND",
                        "source": "RELATIVE_VALUATION_ENGINE",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": as_of.isoformat(),
                        "note": f"Giá trị hợp lý theo P/E tương đối của {symbol}: {m.fair_value.base:,.0f} VND/cổ phiếu.",
                    })
                elif m.method == "Relative P/B" and m.fair_value.base > 0:
                    evidence.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "valuation",
                        "metric": "pb_fair_value",
                        "symbol": symbol,
                        "value": round(m.fair_value.base, 0),
                        "unit": "VND",
                        "source": "RELATIVE_VALUATION_ENGINE",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": as_of.isoformat(),
                        "note": f"Giá trị hợp lý theo P/B tương đối của {symbol}: {m.fair_value.base:,.0f} VND/cổ phiếu.",
                    })
    except Exception:
        pass
    return evidence


def _get_peer_median_evidence(db: Session, symbol: str, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL"):
        return evidence
    try:
        from services.valuation.peers import PeerComparisonEngine
        peer_engine = PeerComparisonEngine(db)
        peer_res = peer_engine.compare_peers(symbol, as_of=as_of)
        if peer_res and peer_res.peer_median_pe is not None:
            group_sym = f"{symbol.upper()}_PEERS"
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "valuation",
                "metric": "peer_median_pe",
                "symbol": group_sym,
                "value": peer_res.peer_median_pe,
                "unit": "multiple",
                "source": "PEER_COMPARISON_ENGINE",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": as_of.isoformat(),
                "note": f"Hệ số P/E trung vị ngành ({peer_res.peer_group_name or peer_res.peer_group_id}): {peer_res.peer_median_pe:.2f} lần (dựa trên {peer_res.peers_evaluated} doanh nghiệp trong ngành).",
            })
            if peer_res.peer_median_pb is not None:
                evidence.append({
                    "claim_type": "FACT",
                    "responsible_module": "valuation",
                    "metric": "peer_median_pb",
                    "symbol": group_sym,
                    "value": peer_res.peer_median_pb,
                    "unit": "multiple",
                    "source": "PEER_COMPARISON_ENGINE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": as_of.isoformat(),
                    "note": f"Hệ số P/B trung vị ngành ({peer_res.peer_group_name or peer_res.peer_group_id}): {peer_res.peer_median_pb:.2f} lần (dựa trên {peer_res.peers_evaluated} doanh nghiệp trong ngành).",
                })
            if peer_res.peer_median_roe is not None:
                evidence.append({
                    "claim_type": "FACT",
                    "responsible_module": "valuation",
                    "metric": "peer_median_roe",
                    "symbol": group_sym,
                    "value": peer_res.peer_median_roe,
                    "unit": "%",
                    "source": "PEER_COMPARISON_ENGINE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": as_of.isoformat(),
                    "note": f"Tỷ suất ROE trung vị ngành ({peer_res.peer_group_name or peer_res.peer_group_id}): {peer_res.peer_median_roe:.2f}%.",
                })
    except Exception:
        pass
    return evidence


def _get_opportunity_evidence(db: Session, symbol: str, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL"):
        return evidence
    try:
        from services.opportunity.scanner import build_opportunity_scanner
        scanner_res = build_opportunity_scanner(
            session=db,
            as_of=as_of,
            universe="ALL",
            symbol=symbol,
        )
        if scanner_res and scanner_res.results:
            item = scanner_res.results[0]
            if item.opportunity_score is not None:
                why_now_texts = [w.get("description", "") for w in (item.why_now or []) if w.get("description")]
                why_str = f" Động lực chính: {'; '.join(why_now_texts[:2])}." if why_now_texts else ""
                evidence.append({
                    "claim_type": "MODEL_OUTPUT",
                    "responsible_module": "opportunity",
                    "metric": "opportunity_score",
                    "symbol": symbol.upper(),
                    "value": round(float(item.opportunity_score), 1),
                    "unit": "score_100",
                    "source": "OPPORTUNITY_ENGINE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": as_of.isoformat(),
                    "note": f"Điểm cơ hội đầu tư định lượng của {symbol.upper()}: {item.opportunity_score:.1f}/100 (độ tin cậy: {item.confidence}).{why_str}",
                })
            if item.risk_score is not None:
                why_not_texts = [w.get("description", "") for w in (item.why_not_now or []) if w.get("description")]
                risk_str = f" Lưu ý rủi ro: {'; '.join(why_not_texts[:2])}." if why_not_texts else ""
                evidence.append({
                    "claim_type": "MODEL_OUTPUT",
                    "responsible_module": "risk",
                    "metric": "risk_score",
                    "symbol": symbol.upper(),
                    "value": round(float(item.risk_score), 1),
                    "unit": "score_100",
                    "source": "OPPORTUNITY_ENGINE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": as_of.isoformat(),
                    "note": f"Điểm rủi ro tổng hợp của {symbol.upper()}: {item.risk_score:.1f}/100.{risk_str}",
                })
    except Exception:
        pass
    return evidence


def _get_dividend_evidence(db: Session, symbol: str, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    try:
        from services.fundamentals.dividends import DividendYieldEngine
        summary = DividendYieldEngine.calculate(db, symbol, as_of)
        if summary.payments:
            evidence.append({
                "claim_type": "FACT" if summary.data_status == "AVAILABLE" else "MODEL_OUTPUT",
                "responsible_module": "corporate_actions",
                "metric": "dividend_yield",
                "symbol": symbol.upper(),
                "value": summary.ttm_dividend_yield,
                "unit": "%",
                "source": "CANONICAL_CORPORATE_ACTION",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": summary.data_status,
                "observation_date": as_of.isoformat(),
                "note": f"Tỷ suất cổ tức tiền mặt 12 tháng gần nhất (TTM) của {symbol}: {summary.ttm_dividend_yield:.2f}% (tổng chi trả {summary.ttm_cash_dividend:,.0f} đ/cp trên thị giá {summary.canonical_price:,.0f} đ). Trạng thái: {summary.data_status}.",
            })
            evidence.append({
                "claim_type": "FACT" if summary.data_status == "AVAILABLE" else "MODEL_OUTPUT",
                "responsible_module": "corporate_actions",
                "metric": "cash_dividend",
                "symbol": symbol.upper(),
                "value": summary.ttm_cash_dividend,
                "unit": "VND/share",
                "source": "CANONICAL_CORPORATE_ACTION",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": summary.data_status,
                "observation_date": as_of.isoformat(),
                "note": f"Tổng mức chi trả cổ tức tiền mặt TTM của {symbol} là {summary.ttm_cash_dividend:,.0f} đ/cp. Tổng cổ tức năm tài chính gần nhất là {summary.fiscal_year_cash_dividend:,.0f} đ/cp (tỷ suất {summary.fiscal_year_dividend_yield:.2f}%). Lũy kế lịch sử: {summary.historical_cumulative_dividend:,.0f} đ/cp.",
            })
    except Exception:
        pass
    return evidence


def _get_screener_evidence(db: Session, screener_spec: Any, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    try:
        from services.screener.engine import StockScreenerEngine, ScreenerCriteria
        engine = StockScreenerEngine(db)
        pe_max = getattr(screener_spec, "pe_max", None)
        roe_min = getattr(screener_spec, "roe_min", None)
        crit = ScreenerCriteria(
            universe="ALL",
            pe_max=pe_max if pe_max is not None else 15.0,
            roe_min=roe_min if roe_min is not None else 15.0,
            limit=100,
        )
        res = engine.screen(crit, as_of=as_of)
        matched_symbols = [m.symbol for m in res.matches]
        evidence.append({
            "claim_type": "FACT",
            "responsible_module": "screener",
            "metric": "screened_count",
            "symbol": "UNIVERSE_ALL",
            "value": res.total_screened,
            "unit": "stocks",
            "source": "STOCK_SCREENER_ENGINE",
            "data_origin": "CANONICAL_DATABASE",
            "freshness": "AVAILABLE",
            "observation_date": as_of.isoformat(),
            "note": f"Tổng số cổ phiếu được rà soát trong toàn bộ vũ trụ đầu tư: {res.total_screened} mã.",
        })
        evidence.append({
            "claim_type": "FACT",
            "responsible_module": "screener",
            "metric": "matched_count",
            "symbol": "UNIVERSE_ALL",
            "value": res.matched_count,
            "unit": "stocks",
            "source": "STOCK_SCREENER_ENGINE",
            "data_origin": "CANONICAL_DATABASE",
            "freshness": "AVAILABLE",
            "observation_date": as_of.isoformat(),
            "note": f"Số lượng cổ phiếu thỏa mãn tiêu chí P/E < {crit.pe_max} và ROE > {crit.roe_min}%: {res.matched_count} mã.",
        })
        top_syms = ", ".join(matched_symbols[:10])
        evidence.append({
            "claim_type": "FACT",
            "responsible_module": "screener",
            "metric": "matching_symbols",
            "symbol": "UNIVERSE_ALL",
            "value": top_syms,
            "unit": "list",
            "source": "STOCK_SCREENER_ENGINE",
            "data_origin": "CANONICAL_DATABASE",
            "freshness": "AVAILABLE",
            "observation_date": as_of.isoformat(),
            "note": f"Danh sách các cổ phiếu tiêu biểu thỏa mãn tiêu chí gồm: {top_syms}.",
        })
        for m in res.matches[:6]:
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "screener",
                "metric": "pe",
                "symbol": m.symbol,
                "value": m.pe,
                "unit": "multiple",
                "source": "STOCK_SCREENER_ENGINE",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": as_of.isoformat(),
                "note": f"Mã {m.symbol}: P/E={m.pe} (nhỏ hơn 15), ROE={m.roe}% (lớn hơn 15%).",
            })
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "screener",
                "metric": "roe",
                "symbol": m.symbol,
                "value": m.roe,
                "unit": "%",
                "source": "STOCK_SCREENER_ENGINE",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": as_of.isoformat(),
                "note": f"Mã {m.symbol}: Tỷ suất sinh lời trên vốn chủ sở hữu ROE={m.roe}%.",
            })
    except Exception:
        pass
    return evidence


class AITools:
    """Whitelisted read-only data tools; quantitative scores are never computed here."""

    @staticmethod
    def get_stock_snapshot(
        symbol: str,
        as_of: Optional[date] = None,
        session: Optional[Session] = None,
    ) -> dict[str, Any]:
        close_session = session is None
        db = session or SessionLocal()
        from services.universe.registry import UniverseRegistry
        resolved = UniverseRegistry.resolve_instrument(db, symbol) if symbol else None
        normalized = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(symbol) or symbol.upper())
        requested_date = as_of or date.today()
        try:
            asset = db.query(Asset).filter(Asset.symbol == normalized).first()
            if asset is None:
                return {
                    "symbol": normalized,
                    "as_of": requested_date.isoformat(),
                    "status": "INSUFFICIENT_DATA",
                    "opportunity_score": None,
                    "risk_score": None,
                    "confidence": "INSUFFICIENT",
                    "why_now": [],
                    "why_not_now": [{
                        "claim_type": "UNCERTAINTY",
                        "text": "Asset is not present in the canonical registry.",
                    }],
                    "what_could_go_wrong": [],
                    "signal_conflict": "INSUFFICIENT_DATA",
                }

            context = build_decision_context(db, normalized, requested_date)
            modules = context.get("snapshot", {}).get("modules", {})
            opportunity = modules.get("opportunity", {})
            risk = modules.get("risk", {})
            return {
                "symbol": normalized,
                "as_of": context["as_of_date"],
                "status": context["decision_state"],
                "opportunity_score": opportunity.get("score"),
                "risk_score": risk.get("overall_score"),
                "confidence": opportunity.get("confidence", "INSUFFICIENT"),
                "why_now": context.get("why_now", []),
                "why_not_now": context.get("why_not_now", []),
                "what_could_go_wrong": context.get("what_would_make_me_wrong", []),
                "signal_conflict": "INSUFFICIENT_DATA",
                "explainability": context.get("explainability", {}),
                "evidence": context.get("evidence", []),
            }
        finally:
            if close_session:
                db.close()

    @staticmethod
    def get_market_context(session: Optional[Session] = None, as_of: Optional[date] = None) -> dict[str, Any]:
        close_session = session is None
        db = session or SessionLocal()
        requested_date = as_of or date.today()
        try:
            market = build_market_dashboard(db, requested_date).model_dump(mode="json")
            macro = get_latest_macro_series(db, requested_date).model_dump(mode="json")
            regime = market.get("market_regime", {})
            breadth = market.get("breadth", {})

            # Build verifiable evidence for market regime & breadth
            market_ev: list[dict[str, Any]] = []
            if regime and regime.get("regime"):
                conf_val = float(regime["confidence"]) if regime.get("confidence") is not None else 1.0
                mom_val = float(regime["momentum_20d"]) if regime.get("momentum_20d") is not None else 0.0
                market_ev.append({
                    "claim_type": "MODEL_OUTPUT",
                    "responsible_module": "regime",
                    "metric": "market_regime",
                    "symbol": "VN100",
                    "value": regime.get("regime"),
                    "unit": "regime",
                    "source": regime.get("model_version") or "vn100_price_breadth_v1",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": regime.get("as_of"),
                    "note": f"Trạng thái chế độ thị trường rổ chỉ số đại diện VN100 (Proxy Context): {regime.get('regime')} (độ tin cậy: {conf_val*100:.0f}%, momentum 20 phiên: {mom_val*100:+.2f}%).",
                })
            if breadth and breadth.get("value") is not None:
                details = breadth.get("details", {})
                adv = details.get("advancing")
                dec = details.get("declining")
                unch = details.get("unchanged")
                pct = float(breadth["value"])
                market_ev.append({
                    "claim_type": "FACT",
                    "responsible_module": "regime",
                    "metric": "market_breadth_pct",
                    "symbol": "VN100",
                    "value": pct,
                    "unit": "%",
                    "source": breadth.get("source") or "vn100_breadth",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": breadth.get("as_of_date"),
                    "note": f"Độ rộng thị trường rổ chỉ số đại diện VN100 (Proxy Context): {pct:.1f}% mã tăng ({adv} mã tăng, {dec} mã giảm, {unch} mã không đổi trên {details.get('covered_members', 100)} mã).",
                })
                if adv is not None:
                    market_ev.append({
                        "claim_type": "FACT",
                        "responsible_module": "regime",
                        "metric": "breadth_advancing",
                        "symbol": "VN100",
                        "value": adv,
                        "unit": "stocks",
                        "source": breadth.get("source") or "vn100_breadth",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": breadth.get("as_of_date"),
                        "note": f"Số lượng cổ phiếu tăng giá trong rổ VN100: {adv} mã.",
                    })
                if dec is not None:
                    market_ev.append({
                        "claim_type": "FACT",
                        "responsible_module": "regime",
                        "metric": "breadth_declining",
                        "symbol": "VN100",
                        "value": dec,
                        "unit": "stocks",
                        "source": breadth.get("source") or "vn100_breadth",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": breadth.get("as_of_date"),
                        "note": f"Số lượng cổ phiếu giảm giá trong rổ VN100: {dec} mã.",
                    })
            # Explicit disclosure for VNINDEX (toàn sàn HOSE) — prevents silent substitution with VN100
            market_ev.append({
                "claim_type": "UNCERTAINTY",
                "responsible_module": "regime",
                "metric": "market_regime_vnindex",
                "symbol": "VNINDEX",
                "value": None,
                "unit": "regime",
                "source": "canonical_database",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "INSUFFICIENT_DATA",
                "observation_date": requested_date.isoformat(),
                "note": "Chỉ số VNINDEX (toàn sàn HOSE) chưa có dữ liệu chuỗi giá trực tiếp trong cơ sở dữ liệu kiểm chứng. Hệ thống cung cấp trạng thái rổ chỉ số VN100 làm bối cảnh đại diện quy mô lớn (Proxy Context).",
            })
            market["evidence"] = market_ev
            return {
                "status": market.get("status", "INSUFFICIENT_DATA"),
                "as_of_date": requested_date.isoformat(),
                "market_regime": regime.get("regime", "INSUFFICIENT_DATA"),
                "regime_confidence": regime.get("confidence"),
                "macro_growth": "INSUFFICIENT_DATA",
                "macro_liquidity": "INSUFFICIENT_DATA",
                "macro_rates": "INSUFFICIENT_DATA",
                "market": market,
                "macro": macro,
            }
        finally:
            if close_session:
                db.close()

    @staticmethod
    def get_recent_events(
        symbol: Optional[str] = None,
        session: Optional[Session] = None,
        as_of: Optional[date] = None,
    ) -> list[dict[str, Any]]:
        events = EventEngine.get_recent_events(
            symbol=symbol,
            session=session,
            as_of=as_of or date.today(),
        )
        return [event.model_dump(mode="json") for event in events]

    @staticmethod
    def get_context(
        symbol: Optional[str | list[str]],
        as_of: date,
        tool_names: Optional[list[str]] = None,
        session: Optional[Session] = None,
        question: Optional[str] = None,
    ) -> dict[str, Any]:
        requested = tool_names or list(TOOL_NAMES)
        unknown = sorted(set(requested) - set(TOOL_NAMES))
        if unknown:
            raise ValueError(f"Unsupported AI tools: {', '.join(unknown)}")

        as_of = as_of or date.today()
        close_session = session is None
        db = session or SessionLocal()
        try:
            from services.universe.registry import UniverseRegistry

            # Normalize to list of symbols
            raw_symbols = [symbol] if isinstance(symbol, str) else (symbol or [])
            norm_symbols: list[str] = []
            for s in raw_symbols:
                if not s:
                    continue
                resolved = UniverseRegistry.resolve_instrument(db, s)
                norm = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(s) or s.upper())
                if norm and norm not in norm_symbols:
                    norm_symbols.append(norm)

            market_context = AITools.get_market_context(session=db, as_of=as_of)

            # If multi-ticker comparison requested
            if len(norm_symbols) > 1:
                combined_evidence: list[dict[str, Any]] = []
                assets_info = []
                primary_decision_state = "INSUFFICIENT_DATA"

                for sym in norm_symbols:
                    asset = db.query(Asset).filter(Asset.symbol == sym).first()
                    if asset:
                        assets_info.append({
                            "symbol": asset.symbol,
                            "name": asset.name,
                            "asset_type": asset.asset_type,
                            "exchange": asset.exchange,
                            "sector": asset.sector,
                            "registry_status": asset.status,
                        })
                        decision = build_decision_context(db, sym, as_of)
                        sym_evidence = decision.get("evidence", []) if decision else []
                        for ev in sym_evidence:
                            ev_copy = dict(ev)
                            ev_copy["symbol"] = sym
                            combined_evidence.append(ev_copy)

                        # Bank metrics expansion
                        bank_ev = _get_bank_evidence(db, asset, as_of)
                        combined_evidence.extend(bank_ev)

                        # DCF and Peer Medians expansion
                        dcf_ev = _get_valuation_dcf_evidence(db, sym, as_of)
                        combined_evidence.extend(dcf_ev)
                        peer_ev = _get_peer_median_evidence(db, sym, as_of)
                        combined_evidence.extend(peer_ev)
                        opp_ev = _get_opportunity_evidence(db, sym, as_of)
                        combined_evidence.extend(opp_ev)

                        if decision and decision.get("decision_state") == "AVAILABLE":
                            primary_decision_state = "AVAILABLE"
                    else:
                        combined_evidence.append({
                            "claim_type": "UNCERTAINTY",
                            "responsible_module": "asset",
                            "metric": "asset_registry",
                            "symbol": sym,
                            "source": "asset_registry",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "INSUFFICIENT_DATA",
                            "note": f"Mã cổ phiếu {sym} không có trong cơ sở dữ liệu kiểm chứng của hệ thống.",
                        })

                # Append commodity evidence and series
                comm_ev, c_series, s_series = _get_commodity_evidence_and_series(db, norm_symbols, as_of, question)
                combined_evidence.extend(comm_ev)

                # Append market context evidence
                for ev in market_context.get("market", {}).get("evidence", []):
                    ev_copy = dict(ev)
                    ev_copy.setdefault("symbol", "VN100")
                    combined_evidence.append(ev_copy)

                results = []
                for name in requested:
                    if name == "asset":
                        results.append({"name": name, "status": "AVAILABLE" if assets_info else "INSUFFICIENT_DATA", "data": assets_info})
                    elif name == "macro":
                        results.append({"name": name, "status": _status(market_context.get("macro")), "data": market_context.get("macro")})
                    elif name == "regime":
                        results.append({"name": name, "status": _status(market_context.get("market", {}).get("market_regime")), "data": market_context.get("market", {}).get("market_regime")})
                    elif name == "evidence":
                        results.append({"name": name, "status": "AVAILABLE" if combined_evidence else "INSUFFICIENT_DATA", "data": combined_evidence})
                    else:
                        results.append({"name": name, "status": "INSUFFICIENT_DATA", "data": None})

                return {
                    "symbol": ", ".join(norm_symbols),
                    "symbols": norm_symbols,
                    "as_of_date": as_of.isoformat(),
                    "decision_state": primary_decision_state,
                    "tools": results,
                    "evidence": combined_evidence,
                    "commodity_series": c_series,
                    "stock_price_series": s_series,
                }

            # Single symbol path (or no symbol)
            normalized = norm_symbols[0] if norm_symbols else None
            asset = db.query(Asset).filter(Asset.symbol == normalized).first() if normalized else None
            decision = build_decision_context(db, normalized, as_of) if normalized else None
            modules = decision.get("snapshot", {}).get("modules", {}) if decision else {}
            events = AITools.get_recent_events(symbol=normalized, session=db, as_of=as_of)
            watchlist = db.query(WatchlistItem).filter(WatchlistItem.asset_id == asset.id).first() if asset else None
            watchlist_data = ({
                "thesis": watchlist.thesis,
                "horizon": watchlist.horizon,
                "invalidation": watchlist.invalidation,
                "last_reviewed_at": watchlist.last_reviewed_at.isoformat() if watchlist.last_reviewed_at else None,
            } if watchlist else None)
            snapshots = db.query(AssetDecisionSnapshot).filter(
                AssetDecisionSnapshot.asset_id == asset.id
            ).order_by(AssetDecisionSnapshot.id.desc()).limit(100).all() if asset else []
            historical = next((
                row.snapshot_data
                for row in snapshots
                if (row.snapshot_data.get("facts", {}).get("as_of_date") or "") <= as_of.isoformat()
            ), None)
            portfolio_data = {
                "portfolio": portfolio_dashboard(db, as_of),
                "portfolio_fit": portfolio_fit(db, as_of),
            }
            evidence = decision.get("evidence", []) if decision else []
            if normalized:
                for ev in evidence:
                    ev.setdefault("symbol", normalized)

            # Bank metrics expansion
            if asset:
                bank_ev = _get_bank_evidence(db, asset, as_of)
                evidence.extend(bank_ev)

            # DCF valuation expansion
            if normalized:
                dcf_ev = _get_valuation_dcf_evidence(db, normalized, as_of)
                evidence.extend(dcf_ev)

            # Peer medians expansion
            if normalized:
                peer_ev = _get_peer_median_evidence(db, normalized, as_of)
                evidence.extend(peer_ev)
                opp_ev = _get_opportunity_evidence(db, normalized, as_of)
                evidence.extend(opp_ev)

            # Dividend expansion (Q15)
            q_lower_str = (question or "").lower()
            if normalized and any(w in q_lower_str for w in ("cổ tức", "dividend", "yield")):
                div_ev = _get_dividend_evidence(db, normalized, as_of)
                evidence.extend(div_ev)

            # Screener expansion (Q19)
            import re
            is_screener = bool(
                normalized in ("ALL", "UNIVERSE", "UNIVERSE_ALL")
                or re.search(r"\b(tìm\s*các\s*cổ\s*phiếu|lọc\s*cổ\s*phiếu|thỏa\s*mãn\s*tiêu\s*chí|bộ\s*lọc|định\s*giá\s*rẻ\s*p\/e|những\s*cổ\s*phiếu\s*nào|cổ\s*phiếu\s*nào\s*đang\s*có)\b", q_lower_str)
                or (re.search(r"\bp\/e\b.*?\b(?:dưới|<|thấp\s*hơn)\b", q_lower_str) and re.search(r"\broe\b.*?\b(?:trên|>|cao\s*hơn)\b", q_lower_str))
            )
            if is_screener:
                scr_ev = _get_screener_evidence(db, None, as_of)
                evidence.extend(scr_ev)

            # Market context & breadth expansion (Q8)
            is_market_query = (
                normalized in (None, "VN100", "VNINDEX")
                or any(k in q_lower_str for k in ("chế độ thị trường", "market regime", "độ rộng", "breadth", "thị trường chứng khoán"))
            )
            if is_market_query:
                for ev in market_context.get("market", {}).get("evidence", []):
                    ev_copy = dict(ev)
                    ev_copy.setdefault("symbol", "VN100")
                    evidence.append(ev_copy)

            # Macro commodity expansion
            comm_ev, c_series, s_series = _get_commodity_evidence_and_series(db, norm_symbols, as_of, question)
            evidence.extend(comm_ev)

            rag_service = DocumentRAGService(session=db)
            rag_docs = rag_service.retrieve_documents(
                query=normalized if normalized else "corporate update",
                ticker=normalized,
                as_of_date=as_of,
                limit=5,
            )
            document_payload = rag_docs if rag_docs["status"] == "AVAILABLE" else {
                "status": "INSUFFICIENT_DATA",
                "documents": [],
                "embedding_provider": rag_docs.get("embedding_provider", {"status": "NOT_CONFIGURED"}),
                "note": "No local document index is currently available; retrieval remains insufficient until a local corpus is indexed.",
            }
            from services.fundamentals.sector_models import get_sector_for_symbol
            tool_data: dict[str, Any] = {
                "asset": ({
                    "symbol": asset.symbol,
                    "name": asset.name,
                    "asset_type": asset.asset_type,
                    "exchange": asset.exchange,
                    "sector": asset.sector or get_sector_for_symbol(asset.symbol) or "GENERAL",
                    "registry_status": asset.status,
                } if asset else None),
                "fundamentals": modules.get("fundamentals"),
                "valuation": modules.get("valuation"),
                "factors": modules.get("factors"),
                "risk": modules.get("risk"),
                "macro": modules.get("macro") if decision else market_context.get("macro"),
                "regime": modules.get("regime") if decision else market_context.get("market", {}).get("market_regime"),
                "events": modules.get("events") if decision else events,
                "opportunity": modules.get("opportunity"),
                "portfolio": portfolio_data,
                "watchlist": watchlist_data,
                "historical_snapshot": historical,
                "evidence": evidence or None,
                "document_retrieval": document_payload,
            }
            results = []
            for name in requested:
                data = tool_data.get(name)
                state = _status(data)
                if name == "document_retrieval":
                    state = "INSUFFICIENT_DATA"
                results.append({"name": name, "status": state, "data": data})

            return {
                "symbol": normalized,
                "symbols": norm_symbols,
                "as_of_date": as_of.isoformat(),
                "decision_state": decision.get("decision_state") if decision else market_context.get("status", "INSUFFICIENT_DATA"),
                "tools": results,
                "evidence": evidence,
                "commodity_series": c_series,
                "stock_price_series": s_series,
            }
        finally:
            if close_session:
                db.close()
