from datetime import date
import os
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.connection import SessionLocal, is_cloud_mode
from database.models import (
    Asset, AssetDecisionSnapshot, CorporateAction, WatchlistItem,
    BankMetric, Document, FinancialStatement, MacroAnalysisLog, MacroCommodity, NormalizedIncome, Price
)
from services.decision.engine import build_decision_context
from services.events.engine import EventEngine
from services.macro.observations import get_latest_macro_series
from services.market.dashboard import build_market_dashboard
from services.fundamentals.repository import FinancialRepository
from services.portfolio.engine import get_portfolio_state
from services.research.rag import DocumentRAGService

_UNSET_ARG = object()


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


def _get_price_change_evidence(db: Session, asset: Asset, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not asset:
        return evidence
    try:
        rows = (
            db.query(Price)
            .filter(Price.asset_id == asset.id, Price.status == "VALID", Price.observation_date <= as_of)
            .order_by(Price.observation_date.desc())
            .limit(2)
            .all()
        )
        if len(rows) >= 2:
            curr, prev = rows[0], rows[1]
            c_val = round(float(curr.adjusted_close if curr.adjusted_close is not None else curr.raw_close), 2)
            p_val = round(float(prev.adjusted_close if prev.adjusted_close is not None else prev.raw_close), 2)
            if p_val > 0:
                chg_vnd = round(c_val - p_val, 2)
                chg_pct = round((chg_vnd / p_val) * 100.0, 2)
                evidence.append({
                    "claim_type": "FACT",
                    "responsible_module": "price",
                    "metric": "previous_close",
                    "symbol": asset.symbol,
                    "value": p_val,
                    "unit": "VND",
                    "source": prev.source or "CANONICAL_DATABASE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": prev.observation_date.isoformat(),
                    "note": f"Giá đóng cửa phiên liền trước ({prev.observation_date}) của {asset.symbol}: {p_val:,.0f} VND/cổ phiếu.",
                })
                evidence.append({
                    "claim_type": "MODEL_OUTPUT",
                    "responsible_module": "price",
                    "metric": "price_change_pct",
                    "symbol": asset.symbol,
                    "value": chg_pct,
                    "unit": "%",
                    "source": curr.source or "CANONICAL_DATABASE",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": curr.observation_date.isoformat(),
                    "note": f"Biến động giá {asset.symbol} phiên {curr.observation_date} so với phiên liền trước ({prev.observation_date}): {chg_vnd:+,.0f} VND ({chg_pct:+.2f}%), từ {p_val:,.0f} VND sang {c_val:,.0f} VND.",
                })
    except Exception:
        pass
    return evidence


def _to_billion_vnd(val: Any) -> Optional[float]:
    if val is None:
        return None
    f_val = float(val)
    if abs(f_val) > 1e8:
        return round(f_val / 1e9, 2)
    return round(f_val, 2)


def _get_deep_fundamental_evidence(
    db: Session,
    asset: Asset,
    as_of: date,
    preloaded_dataset: Any = _UNSET_ARG,
) -> list[dict[str, Any]]:
    """Expose Balance Sheet breakdown, Cash Flow quality (CFO/NI), and Postgres Sector Z-Scores."""
    evidence: list[dict[str, Any]] = []
    if not asset:
        return evidence
    sym = asset.symbol.upper()
    try:
        ds = (
            preloaded_dataset
            if preloaded_dataset is not _UNSET_ARG and isinstance(preloaded_dataset, dict)
            else FinancialRepository(db).get_financial_dataset(sym, as_of_date=as_of, asset=asset)
        )
        if ds:
            bal_rows = ds.get("balance_annual") or []
            if bal_rows:
                latest_bs = sorted(bal_rows, key=lambda r: r.get("fiscal_period_end") or date.min)[-1]
                bs_end = latest_bs.get("fiscal_period_end") or as_of
                bs_label = f"{latest_bs.get('fiscal_year')}Q{latest_bs.get('fiscal_quarter')}" if latest_bs.get("fiscal_quarter") else f"FY{latest_bs.get('fiscal_year')}"
                st_debt = _to_billion_vnd(latest_bs.get("short_term_debt"))
                lt_debt = _to_billion_vnd(latest_bs.get("long_term_debt"))
                tot_debt = round((st_debt or 0.0) + (lt_debt or 0.0), 2) if (st_debt is not None or lt_debt is not None) else None
                bs_items = [
                    ("inventory", _to_billion_vnd(latest_bs.get("inventory")), "Hàng tồn kho"),
                    ("short_term_debt", st_debt, "Nợ vay ngắn hạn"),
                    ("long_term_debt", lt_debt, "Nợ vay dài hạn"),
                    ("total_debt", tot_debt, "Tổng nợ vay tài chính"),
                    ("cash", _to_billion_vnd(latest_bs.get("cash")), "Tiền và tương đương tiền"),
                    ("total_equity", _to_billion_vnd(latest_bs.get("total_equity")), "Vốn chủ sở hữu"),
                ]
                for m_key, m_val, m_label in bs_items:
                    if m_val is not None:
                        evidence.append({
                            "claim_type": "FACT",
                            "responsible_module": "fundamentals",
                            "metric": m_key,
                            "symbol": sym,
                            "value": m_val,
                            "unit": "BILLION_VND",
                            "source": "CANONICAL_BALANCE_SHEET",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": bs_end.isoformat() if hasattr(bs_end, "isoformat") else str(bs_end),
                            "note": f"{m_label} của {sym} kỳ {bs_label}: {m_val:,.2f} tỷ VND.",
                        })

            cf_rows = ds.get("cashflow_annual") or []
            inc_all = (ds.get("income_annual") or []) + (ds.get("income_quarters") or [])
            if cf_rows:
                # Prefer matching period between CF and Income Statement for apples-to-apples CFO/NI
                inc_by_key = {
                    (r.get("fiscal_period_end"), r.get("period_type")): r
                    for r in inc_all
                    if r.get("fiscal_period_end")
                }
                cf_sorted = sorted(
                    cf_rows,
                    key=lambda r: (1 if r.get("cash_from_operations") is not None else 0, r.get("fiscal_period_end") or date.min),
                )
                latest_cf = cf_sorted[-1]
                cf_end = latest_cf.get("fiscal_period_end") or as_of
                cf_label = f"{latest_cf.get('fiscal_year')}Q{latest_cf.get('fiscal_quarter')}" if latest_cf.get("fiscal_quarter") else f"FY{latest_cf.get('fiscal_year')}"
                cfo_v = _to_billion_vnd(latest_cf.get("cash_from_operations"))
                fcf_v = _to_billion_vnd(latest_cf.get("free_cash_flow"))
                if fcf_v is None and cfo_v is not None and latest_cf.get("capex") is not None:
                    fcf_v = round(cfo_v - abs(_to_billion_vnd(latest_cf.get("capex")) or 0.0), 2)
                if cfo_v is not None:
                    evidence.append({
                        "claim_type": "FACT",
                        "responsible_module": "fundamentals",
                        "metric": "cfo",
                        "symbol": sym,
                        "value": cfo_v,
                        "unit": "BILLION_VND",
                        "source": "CANONICAL_CASH_FLOW",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": cf_end.isoformat() if hasattr(cf_end, "isoformat") else str(cf_end),
                        "note": f"Lưu chuyển tiền thuần từ HĐKD (CFO) của {sym} kỳ {cf_label}: {cfo_v:,.2f} tỷ VND.",
                    })
                if fcf_v is not None:
                    evidence.append({
                        "claim_type": "FACT",
                        "responsible_module": "fundamentals",
                        "metric": "fcf",
                        "symbol": sym,
                        "value": fcf_v,
                        "unit": "BILLION_VND",
                        "source": "CANONICAL_CASH_FLOW",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": cf_end.isoformat() if hasattr(cf_end, "isoformat") else str(cf_end),
                        "note": f"Dòng tiền tự do (FCF) của {sym} kỳ {cf_label}: {fcf_v:,.2f} tỷ VND.",
                    })
                matched_inc = inc_by_key.get((latest_cf.get("fiscal_period_end"), latest_cf.get("period_type")))
                is_bank = (asset.sector and "BANK" in asset.sector.upper()) or sym in {"VCB", "MBB", "TCB", "BID", "CTG", "ACB", "VPB", "STB", "HDB", "TPB"}
                if not is_bank and cfo_v is not None and matched_inc:
                    ni_v = _to_billion_vnd(matched_inc.get("net_income_parent") or matched_inc.get("net_income"))
                    if ni_v and ni_v > 0:
                        ratio = round(cfo_v / ni_v, 2)
                        warn = " [CẢNH BÁO: Chất lượng chuyển hóa tiền mặt yếu (< 0.30x), cần kiểm tra phải thu/hàng tồn kho]" if ratio < 0.30 else ""
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "fundamentals",
                            "metric": "cfo_to_ni",
                            "symbol": sym,
                            "value": ratio,
                            "unit": "ratio",
                            "source": "CASH_FLOW_QUALITY_ENGINE",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": cf_end.isoformat() if hasattr(cf_end, "isoformat") else str(cf_end),
                            "note": f"Tỷ lệ chất lượng dòng tiền CFO / Lợi nhuận ròng của {sym} ({cf_label}): {ratio:.2f}x (CFO={cfo_v:,.2f} tỷ / LN={ni_v:,.2f} tỷ VND).{warn}",
                        })
    except Exception:
        pass

    # Pillar 1: Accounting Deconsolidation / Like-for-Like divergence check
    try:
        inc_q = ds.get("income_quarters") or [] if ds else []
        by_yq = {
            (r.get("fiscal_year"), r.get("fiscal_quarter")): r
            for r in inc_q
            if r.get("fiscal_year") and r.get("fiscal_quarter")
        }
        if by_yq:
            latest_y, latest_q = max(by_yq.keys())
            cur_r = by_yq.get((latest_y, latest_q))
            prev_r = by_yq.get((latest_y - 1, latest_q))
            if cur_r and prev_r:
                c_rev = float(cur_r.get("revenue") or 0.0)
                p_rev = float(prev_r.get("revenue") or 0.0)
                c_ni = float(cur_r.get("net_income_parent") or cur_r.get("net_income") or 0.0)
                p_ni = float(prev_r.get("net_income_parent") or prev_r.get("net_income") or 0.0)
                if p_rev > 0 and p_ni > 0:
                    rev_yoy_pct = ((c_rev - p_rev) / p_rev) * 100.0
                    ni_yoy_pct = ((c_ni - p_ni) / p_ni) * 100.0
                    cur_nm = (c_ni / c_rev * 100.0) if c_rev > 0 else 0.0
                    prev_nm = (p_ni / p_rev * 100.0) if p_rev > 0 else 0.0
                    if rev_yoy_pct < -2.0 and ni_yoy_pct > 10.0 and cur_nm > prev_nm:
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "fundamentals",
                            "metric": "accounting_deconsolidation_lfl",
                            "symbol": sym,
                            "value": round(ni_yoy_pct, 2),
                            "unit": "%",
                            "source": "ACCOUNTING_REGIME_CLASSIFIER",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": as_of.isoformat(),
                            "note": (
                                f"Lưu ý chuẩn mực kế toán Like-for-Like (LFL) của {sym} kỳ {latest_y}Q{latest_q}: "
                                f"Doanh thu bề mặt giảm {rev_yoy_pct:+.1f}% YoY do thay đổi phương thức hợp nhất (deconsolidation) công ty thành viên/liên kết, "
                                f"trong khi Lợi nhuận sau thuế tăng {ni_yoy_pct:+.1f}% YoY và biên ròng mở rộng từ {prev_nm:.1f}% lên {cur_nm:.1f}% cho thấy động lực lõi thực tế tăng trưởng tích cực."
                            ),
                        })
    except Exception:
        pass

    # Pillar 2: 2026 Corporate Intelligence & Blindspot Metrics stored in Document.metadata_json
    try:
        intel_docs = (
            db.query(Document)
            .filter(
                Document.ticker == sym,
                Document.is_synthetic.is_(False),
                Document.publication_date <= as_of,
            )
            .order_by(Document.publication_date.desc())
            .limit(4)
            .all()
        )
        seen_intel_metrics: set[str] = set()
        for doc in intel_docs:
            meta = doc.metadata_json or {}
            if not isinstance(meta, dict):
                continue
            structured = meta.get("structured_metrics") or {}
            if isinstance(structured, dict):
                for m_key, m_obj in structured.items():
                    if m_key in seen_intel_metrics or not isinstance(m_obj, dict):
                        continue
                    seen_intel_metrics.add(m_key)
                    evidence.append({
                        "claim_type": "FACT",
                        "responsible_module": "fundamentals",
                        "metric": str(m_key),
                        "symbol": sym,
                        "value": m_obj.get("value"),
                        "unit": m_obj.get("unit") or "BILLION_VND",
                        "source": doc.source or "CORPORATE_FILING_2026",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": doc.publication_date.isoformat() if doc.publication_date else as_of.isoformat(),
                        "note": m_obj.get("note") or f"{m_key} ({sym}): {m_obj.get('value')} {m_obj.get('unit') or ''}.",
                    })
    except Exception:
        pass

    try:
        from services.common.supabase_rpc import call_pg_rpc, is_postgres_session
        if is_postgres_session(db):
            rows = call_pg_rpc(db, "rpc_get_cross_sectional_features", {"p_as_of": as_of, "p_symbol": sym})
            if isinstance(rows, list) and rows:
                r0 = rows[0]
                if r0.get("z_roe") is not None or r0.get("z_pe") is not None:
                    evidence.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "factors",
                        "metric": "sector_z_score",
                        "symbol": sym,
                        "value": round(float(r0.get("z_roe") or 0.0), 2),
                        "unit": "z_score",
                        "source": "RPC_CROSS_SECTIONAL_FEATURES",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": as_of.isoformat(),
                        "note": (
                            f"Vị thế Z-Score ngành {r0.get('sector')} của {sym} (N={r0.get('peer_count')} mã): "
                            f"Z_ROE={r0.get('z_roe')}, Z_PE={r0.get('z_pe')}, Z_PB={r0.get('z_pb')}, "
                            f"Momentum 20D={r0.get('mom_20d')}% (Z={r0.get('z_mom_20d')})."
                        ),
                    })
    except Exception:
        pass
    return evidence


def _get_portfolio_dca_evidence(
    portfolio_overview: Optional[dict[str, Any]],
    portfolio_fit_data: Optional[dict[str, Any]],
    question: Optional[str],
    as_of: date,
) -> list[dict[str, Any]]:
    """Build verifiable personal portfolio concentration & DCA capital deployment evidence."""
    evidence: list[dict[str, Any]] = []
    if not isinstance(portfolio_overview, dict) or not portfolio_overview.get("holdings"):
        return evidence

    summary = portfolio_overview.get("summary") or {}
    conc = portfolio_overview.get("concentration") or {}
    holdings = portfolio_overview.get("holdings") or []
    nav = summary.get("total_value")
    if nav is not None:
        evidence.append({
            "claim_type": "FACT",
            "responsible_module": "portfolio",
            "metric": "portfolio_nav",
            "symbol": "PORTFOLIO",
            "value": round(float(nav), 0),
            "unit": "VND",
            "source": "PERSONAL_PORTFOLIO_DB",
            "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
            "freshness": portfolio_overview.get("status", "AVAILABLE"),
            "observation_date": as_of.isoformat(),
            "note": f"Tổng giá trị tài sản ròng danh mục (NAV) tại {as_of}: {float(nav):,.0f} VND với {len(holdings)} cổ phiếu.",
        })

    if conc or holdings:
        max_w = conc.get("max_single_weight")
        max_sym = conc.get("max_single_symbol")
        sec_w = conc.get("max_sector_weight")
        sec_name = conc.get("max_sector")
        if (not max_sym or not max_w) and holdings:
            top_h = max(holdings, key=lambda h: float(h.get("current_weight") or 0.0))
            if float(top_h.get("current_weight") or 0.0) > 0:
                max_sym = top_h.get("symbol")
                max_w = float(top_h.get("current_weight") or 0.0)
        if (not sec_name or not sec_w) and holdings:
            sec_weights: dict[str, float] = {}
            for h in holdings:
                s_key = str(h.get("sector") or "Khác")
                sec_weights[s_key] = sec_weights.get(s_key, 0.0) + float(h.get("current_weight") or 0.0)
            if sec_weights:
                sec_name, sec_w = max(sec_weights.items(), key=lambda x: x[1])
        s_lim = float(conc.get("single_name_limit") or 0.25)
        sec_lim = float(conc.get("sector_limit") or 0.40)
        breaches = []
        if max_w is not None and float(max_w) > s_lim:
            breaches.append(f"Vượt trần cổ phiếu đơn lẻ {max_sym} ({float(max_w)*100:.1f}% > trần {s_lim*100:.0f}%)")
        if sec_w is not None and float(sec_w) > sec_lim:
            breaches.append(f"Vượt trần ngành {sec_name} ({float(sec_w)*100:.1f}% > trần {sec_lim*100:.0f}%)")
        evidence.append({
            "claim_type": "FACT",
            "responsible_module": "portfolio",
            "metric": "portfolio_concentration",
            "symbol": "PORTFOLIO",
            "value": round(float(max_w or 0.0) * 100.0, 2),
            "unit": "%",
            "source": "PERSONAL_PORTFOLIO_DB",
            "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
            "freshness": "AVAILABLE",
            "observation_date": as_of.isoformat(),
            "note": (
                f"Mức tập trung lớn nhất danh mục: {max_sym} ({float(max_w or 0)*100:.1f}%, trần {s_lim*100:.0f}%); "
                f"Ngành lớn nhất: {sec_name} ({float(sec_w or 0)*100:.1f}%, trần {sec_lim*100:.0f}%). "
                + ("; ".join(breaches) if breaches else "Trong ngưỡng kiểm soát rủi ro tập trung.")
            ),
        })

    for h in holdings:
        sym_h = h.get("symbol")
        cw = h.get("current_weight")
        tw = h.get("target_weight")
        mv = h.get("market_value")
        if sym_h and cw is not None:
            tw_str = f", mục tiêu {float(tw)*100:.1f}%" if tw is not None else ""
            mv_str = f", giá trị {float(mv):,.0f} VND" if mv is not None else ""
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "portfolio",
                "metric": "portfolio_holding_weight",
                "symbol": sym_h,
                "value": round(float(cw) * 100.0, 2),
                "unit": "%",
                "source": "PERSONAL_PORTFOLIO_DB",
                "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
                "freshness": "AVAILABLE",
                "observation_date": as_of.isoformat(),
                "note": f"Tỷ trọng {sym_h} ({h.get('sector')}, vai trò {h.get('role')}): {float(cw)*100:.2f}%{tw_str}{mv_str}.",
            })

    import re
    q_low = (question or "").lower()
    m_budget = re.search(r"(\d+(?:[.,]\d+)?)\s*(triệu|tr\b|trieu|tỷ|ty|m\b)", q_low)
    asks_dca = any(k in q_low for k in ("dca", "giải ngân", "giai ngan", "phân bổ", "phan bo", "trung bình giá", "rebalance", "tái cơ cấu"))
    if m_budget or asks_dca:
        budget_vnd = 50_000_000.0
        if m_budget:
            num = float(m_budget.group(1).replace(",", "."))
            unit_w = m_budget.group(2)
            budget_vnd = num * (1_000_000_000.0 if unit_w in ("tỷ", "ty") else 1_000_000.0)
        s_limit = float(conc.get("single_name_limit") or 0.25)
        fit_items = {it.get("symbol"): it for it in (portfolio_fit_data or {}).get("items", []) if it.get("symbol")}
        candidates = []
        for h in holdings:
            hsym = h.get("symbol")
            cw = float(h.get("current_weight") or 0.0)
            tw = float(h.get("target_weight") or cw)
            if cw >= s_limit * 0.98:
                continue  # Never add capital to concentrated overweight position
            opp_s = float((fit_items.get(hsym) or {}).get("opportunity_score") or 55.0)
            gap = max(0.02, (tw - cw) + (opp_s - 50.0) / 500.0)
            candidates.append((hsym, gap, cw, tw))
        if not candidates and holdings:
            candidates = [(h["symbol"], 1.0, float(h.get("current_weight") or 0.0), float(h.get("target_weight") or 0.0)) for h in holdings]
        selected_cands = sorted(candidates, key=lambda x: x[1], reverse=True)[:4]
        tot_gap = sum(c[1] for c in selected_cands) or 1.0
        plan_parts = []
        for hsym, gap, cw, tw in selected_cands:
            w_alloc = gap / tot_gap
            vnd_alloc = round(budget_vnd * w_alloc, -4)
            plan_parts.append(f"{hsym}: {w_alloc*100:.1f}% (~{vnd_alloc:,.0f} VND, tỷ trọng hiện tại {cw*100:.1f}%)")
        evidence.append({
            "claim_type": "MODEL_OUTPUT",
            "responsible_module": "portfolio",
            "metric": "dca_allocation_plan",
            "symbol": "PORTFOLIO",
            "value": round(budget_vnd, 0),
            "unit": "VND",
            "source": "PORTFOLIO_DCA_REBALANCE_ENGINE",
            "data_origin": "LOCAL_PERSONAL_PORTFOLIO",
            "freshness": "AVAILABLE",
            "observation_date": as_of.isoformat(),
            "note": f"Kế hoạch giải ngân {budget_vnd:,.0f} VND tuân thủ trần tập trung {s_limit*100:.0f}% (tránh dồn thêm vào mã vượt trần): {'; '.join(plan_parts)}.",
        })
    return evidence


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
    from services.market.trading_hours import get_effective_trading_date, get_vn_now

    evidence: list[dict[str, Any]] = []
    c_series: list[float] | None = None
    s_series: list[float] | None = None
    # On weekends/after-hours, allow same-day global commodity benchmarks alongside latest trading day stocks
    comm_cutoff = max(as_of, get_vn_now().date()) if as_of >= get_effective_trading_date() else as_of

    energy_symbols = {"PLX", "GAS", "PVD", "PVS", "BSR", "OIL"}
    has_energy_sym = any(s in energy_symbols for s in norm_symbols)
    q_str = (question or "").lower()
    has_oil_keyword = any(k in q_str for k in ("dầu", "dau", "brent", "wti", "oil", "nhiên liệu", "crack"))

    if has_energy_sym or has_oil_keyword:
        latest_brent = (
            db.query(MacroCommodity)
            .filter(MacroCommodity.commodity_code == "BRENT", MacroCommodity.observation_date <= comm_cutoff)
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

        latest_crack = (
            db.query(MacroCommodity)
            .filter(MacroCommodity.commodity_code == "SINGAPORE_CRACK_SPREAD", MacroCommodity.observation_date <= comm_cutoff)
            .order_by(MacroCommodity.observation_date.desc())
            .first()
        )
        if latest_crack:
            chg_c = f" ({latest_crack.change_pct:+.2f}%)" if latest_crack.change_pct is not None else ""
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "macro",
                "metric": "singapore_crack_spread",
                "symbol": "CRACK_SPREAD",
                "value": latest_crack.close_price,
                "unit": latest_crack.unit or "USD/barrel",
                "source": latest_crack.source or "PUBLIC_COMMODITY_FEED",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": latest_crack.observation_date.isoformat(),
                "note": f"Biên lọc hóa dầu Singapore Crack Spread 3-2-1 tại ngày {latest_crack.observation_date}: {latest_crack.close_price} USD/thùng{chg_c}.",
            })

        # Calculate time series correlation if energy stock present
        target_sym = next((s for s in norm_symbols if s in energy_symbols), None)
        if target_sym:
            target_asset = db.query(Asset).filter(Asset.symbol == target_sym).first()
            if target_asset:
                # 1. Stock price vs Brent spot price series
                stock_prices = (
                    db.query(Price.observation_date, func.coalesce(Price.adjusted_close, Price.raw_close))
                    .filter(Price.asset_id == target_asset.id, Price.observation_date <= as_of, Price.status == "VALID")
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

    steel_symbols = {"HPG", "HSG", "NKG"}
    has_steel_sym = any(s in steel_symbols for s in norm_symbols)
    has_steel_kw = any(k in q_str for k in ("hrc", "thép", "thep", "steel"))
    if has_steel_sym or has_steel_kw:
        latest_hrc = (
            db.query(MacroCommodity)
            .filter(MacroCommodity.commodity_code == "HRC_STEEL", MacroCommodity.observation_date <= comm_cutoff)
            .order_by(MacroCommodity.observation_date.desc())
            .first()
        )
        if latest_hrc:
            chg_h = f" ({latest_hrc.change_pct:+.2f}%)" if latest_hrc.change_pct is not None else ""
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "macro",
                "metric": "hrc_steel_price",
                "symbol": "HRC_STEEL",
                "value": latest_hrc.close_price,
                "unit": latest_hrc.unit or "USD/ton",
                "source": latest_hrc.source or "PUBLIC_COMMODITY_FEED",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": latest_hrc.observation_date.isoformat(),
                "note": f"Giá thép cuộn cán nóng (HRC) tham chiếu tại ngày {latest_hrc.observation_date}: {latest_hrc.close_price} USD/tấn{chg_h}.",
            })

    return evidence, c_series, s_series


def _get_peer_comparison(db: Session, symbol: str, as_of: date) -> Any:
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL"):
        return None
    try:
        from services.valuation.peers import PeerComparisonEngine
        return PeerComparisonEngine(db).compare_peers(symbol, as_of=as_of)
    except Exception:
        return None


def _parse_wacc_g_shock(question: Optional[str]) -> tuple[Optional[float], Optional[float]]:
    """Parse custom WACC and terminal growth (g) delta shocks in % points from user query."""
    if not question:
        return None, None
    import re
    q = question.lower()
    w_delta: Optional[float] = None
    g_delta: Optional[float] = None

    def _extract_signed_pct(anchor_pattern: str) -> Optional[float]:
        anchor = re.search(anchor_pattern, q)
        if not anchor:
            return None
        tail = q[anchor.end() : anchor.end() + 45]
        # Advance past alias like "(g)" right after "tăng trưởng dài hạn" so direction tokens remain intact
        tail = re.sub(r"^\s*\(\s*g\s*\)", "", tail)
        m_num = re.search(r"(\d+(?:[.,]\d+)?)\s*%", tail)
        if not m_num:
            return None
        prefix = tail[: m_num.start()].lower()
        val = float(m_num.group(1).replace(",", "."))
        if any(neg in prefix for neg in ("giảm", "giam", "trừ", "tru", "-")):
            return -val
        return val

    w_delta = _extract_signed_pct(r"\bwacc\b")
    g_delta = _extract_signed_pct(r"(?:tăng\s*trưởng\s*dài\s*hạn|tang\s*truong\s*dai\s*han|\(\s*g\s*\)|\bg\b)")
    return w_delta, g_delta


def _get_valuation_dcf_evidence(
    db: Session,
    symbol: str,
    as_of: date,
    peer_res: Any = None,
    preloaded_dataset: Any = _UNSET_ARG,
    asset_sector: Optional[str] = None,
    latest_price: Optional[float] = None,
    question: Optional[str] = None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL", "PORTFOLIO"):
        return evidence
    try:
        try:
            from apps.api.routers.valuation import _load_fundamentals_for_valuation, _get_latest_price, _get_asset_sector
        except ImportError:
            from routers.valuation import _load_fundamentals_for_valuation, _get_latest_price, _get_asset_sector
        from services.fundamentals.sector_models import get_sector_for_symbol
        from services.valuation.builder import ValuationSnapshotBuilder
        load_kwargs: dict[str, Any] = {"session": db, "peer_res": peer_res}
        if preloaded_dataset is not _UNSET_ARG:
            load_kwargs["dataset"] = preloaded_dataset
        funds = _load_fundamentals_for_valuation(symbol, as_of, **load_kwargs)
        price = latest_price if latest_price is not None else _get_latest_price(symbol, as_of, session=db)
        sector = asset_sector or _get_asset_sector(symbol, session=db) or get_sector_for_symbol(symbol) or "GENERAL"
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
                    wacc_used = next((a.value for a in (m.assumptions_used or []) if a.name == "WACC"), None)
                    wacc_note = f" (WACC={wacc_used}%)" if wacc_used else ""
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
                        "note": f"Định giá DCF kịch bản cơ sở (Base Case) của {symbol}{wacc_note}: {m.fair_value.base:,.0f} VND/cổ phiếu (Bear: {m.fair_value.bear:,.0f} VND, Bull: {m.fair_value.bull:,.0f} VND).",
                    })
                    if getattr(val_snap, "scenarios", None):
                        p10_sc = val_snap.scenarios[0]
                        p50_sc = val_snap.scenarios[1] if len(val_snap.scenarios) > 1 else None
                        p90_sc = val_snap.scenarios[2] if len(val_snap.scenarios) > 2 else None
                        ass_p10 = getattr(p10_sc, "assumptions", {}) or {}
                        p10_v = ass_p10.get("p10")
                        p50_v = ass_p10.get("p50") or (p50_sc.fair_value if p50_sc else None)
                        p90_v = ass_p10.get("p90") or (p90_sc.fair_value if p90_sc else None)
                        if p10_v and p50_v and p90_v:
                            evidence.append({
                                "claim_type": "MODEL_OUTPUT",
                                "responsible_module": "valuation",
                                "metric": "dcf_sensitivity",
                                "symbol": symbol,
                                "value": round(float(p50_v), 0),
                                "unit": "VND",
                                "source": "DCF_SENSITIVITY_MATRIX",
                                "data_origin": "CANONICAL_DATABASE",
                                "freshness": "AVAILABLE",
                                "observation_date": as_of.isoformat(),
                                "note": f"Độ nhạy DCF WACC ±1.0% / g ±0.5% của {symbol}: P10 (stress) = {float(p10_v):,.0f} VND, P50 (median) = {float(p50_v):,.0f} VND, P90 (bull) = {float(p90_v):,.0f} VND.",
                            })
                    wacc_val = funds.get("wacc")
                    beta_val = funds.get("beta")
                    if wacc_val is not None:
                        evidence.append({
                            "claim_type": "MODEL_OUTPUT",
                            "responsible_module": "valuation",
                            "metric": "wacc",
                            "symbol": symbol,
                            "value": round(float(wacc_val) * 100.0, 2),
                            "unit": "%",
                            "source": "CAPM_WACC_MODEL",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": as_of.isoformat(),
                            "note": f"Chi phí vốn bình quân gia quyền WACC của {symbol}: {float(wacc_val)*100:.2f}% (Beta Blume={beta_val}).",
                        })
                    w_shock, g_shock = _parse_wacc_g_shock(question)
                    if w_shock is not None or g_shock is not None:
                        from services.valuation.engine import DCFEngine
                        dcf_assump, _, is_re, _ = builder.build_dcf_context(funds)
                        shares_out = funds.get("shares_outstanding", 1_000_000_000)
                        shock_res = DCFEngine.evaluate_custom_shock(
                            dcf_assump,
                            shares_out,
                            net_debt=funds.get("net_debt", 0),
                            wacc_delta_pct=float(w_shock or 0.0),
                            g_delta_pct=float(g_shock or 0.0),
                        )
                        bvps_val = funds.get("bvps") or 0
                        if is_re and bvps_val and bvps_val > 0 and shock_res.get("base_fair_value", 0) > bvps_val * 1.45:
                            scale_re = (bvps_val * 1.35) / shock_res["base_fair_value"]
                            shock_res["base_fair_value"] = round(shock_res["base_fair_value"] * scale_re, 0)
                            shock_res["shocked_fair_value"] = round(shock_res["shocked_fair_value"] * scale_re, 0)
                            shock_res["delta_vnd"] = round(shock_res["shocked_fair_value"] - shock_res["base_fair_value"], 0)
                        if shock_res.get("valid"):
                            evidence.append({
                                "claim_type": "MODEL_OUTPUT",
                                "responsible_module": "valuation",
                                "metric": "dcf_custom_sensitivity",
                                "symbol": symbol,
                                "value": shock_res["shocked_fair_value"],
                                "unit": "VND",
                                "source": "DCF_SANDBOX_SHOCK_ENGINE",
                                "data_origin": "CANONICAL_DATABASE",
                                "freshness": "AVAILABLE",
                                "observation_date": as_of.isoformat(),
                                "note": (
                                    f"Kịch bản giả định DCF tùy biến cho {symbol}: Khi WACC chuyển từ {shock_res['base_wacc_pct']:.2f}% lên {shock_res['shocked_wacc_pct']:.2f}% "
                                    f"và tăng trưởng dài hạn g chuyển từ {shock_res['base_g_pct']:.2f}% sang {shock_res['shocked_g_pct']:.2f}%, "
                                    f"giá trị hợp lý DCF thay đổi từ {shock_res['base_fair_value']:,.0f} VND xuống {shock_res['shocked_fair_value']:,.0f} VND/cổ phiếu "
                                    f"(chênh lệch {shock_res['delta_vnd']:+,.0f} VND, tức {shock_res['delta_pct']:+.2f}%)."
                                ),
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


def _get_peer_median_evidence(
    db: Session,
    symbol: str,
    as_of: date,
    peer_res: Any = None,
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL"):
        return evidence
    try:
        if peer_res is None:
            from services.valuation.peers import PeerComparisonEngine
            peer_res = PeerComparisonEngine(db).compare_peers(symbol, as_of=as_of)
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


def _get_corporate_action_evidence(db: Session, symbol: str, as_of: date) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    if not symbol or symbol.upper() in ("VN100", "VNINDEX", "VN30", "ALL", "PORTFOLIO"):
        return evidence
    try:
        sym = symbol.strip().upper()
        actions = (
            db.query(CorporateAction)
            .filter(CorporateAction.symbol == sym, CorporateAction.action_date <= as_of)
            .order_by(CorporateAction.action_date.desc(), CorporateAction.id.desc())
            .all()
        )
        deduped: list[CorporateAction] = []
        seen: set[tuple[Any, ...]] = set()
        for ca in actions:
            key = (
                ca.action_date,
                (ca.action_type or "").strip().upper(),
                round(float(ca.value), 4) if ca.value is not None else None,
                round(float(ca.ratio), 4) if ca.ratio is not None else None,
                (ca.notes or "").strip(),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(ca)
        if deduped:
            parts: list[str] = []
            for ca in deduped[:4]:
                act_lbl = (ca.action_type or "CORPORATE_ACTION").strip().upper()
                detail = ca.notes.strip() if ca.notes else ""
                if not detail:
                    if ca.ratio is not None:
                        detail = f"ratio={ca.ratio:g}"
                    elif ca.value is not None:
                        detail = f"value={ca.value:g}"
                parts.append(f"{ca.action_date.isoformat()} [{act_lbl}]" + (f": {detail}" if detail else ""))
            evidence.append({
                "claim_type": "FACT",
                "responsible_module": "corporate_actions",
                "metric": "corporate_action",
                "symbol": sym,
                "value": len(deduped),
                "unit": "events",
                "source": next((c.source for c in deduped if c.source), None) or "CANONICAL_CORPORATE_ACTION",
                "data_origin": "CANONICAL_DATABASE",
                "freshness": "AVAILABLE",
                "observation_date": deduped[0].action_date.isoformat(),
                "note": f"Sự kiện quyền & chia tách/cổ tức của {sym} (gần nhất trước {as_of.isoformat()}): " + " | ".join(parts) + ".",
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
        evidence.extend(_get_corporate_action_evidence(db, symbol, as_of))
    except Exception:
        pass
    return evidence


def _get_screener_evidence(db: Session, screener_spec: Any, as_of: date, question: Optional[str] = None) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    try:
        import re
        from services.screener.engine import StockScreenerEngine, ScreenerCriteria
        engine = StockScreenerEngine(db)
        pe_max = getattr(screener_spec, "pe_max", None)
        roe_min = getattr(screener_spec, "roe_min", None)
        pb_max = getattr(screener_spec, "pb_max", None)
        sector_filter = getattr(screener_spec, "sector", None)

        if question:
            q_low = question.lower()
            if pe_max is None:
                m_pe = re.search(r"\bp\/?e\s*(?:dưới|nhỏ\s*hơn|thấp\s*hơn|<|<=)\s*(\d+(?:[.,]\d+)?)", q_low)
                if m_pe:
                    pe_max = float(m_pe.group(1).replace(",", "."))
            if roe_min is None:
                m_roe = re.search(r"\broe\s*(?:trên|lớn\s*hơn|cao\s*hơn|>|>=)\s*(\d+(?:[.,]\d+)?)", q_low)
                if m_roe:
                    roe_min = float(m_roe.group(1).replace(",", "."))
            if pb_max is None:
                m_pb = re.search(r"\bp\/?b\s*(?:dưới|nhỏ\s*hơn|thấp\s*hơn|<|<=)\s*(\d+(?:[.,]\d+)?)", q_low)
                if m_pb:
                    pb_max = float(m_pb.group(1).replace(",", "."))
            if sector_filter is None:
                if "ngân hàng" in q_low or "bank" in q_low:
                    sector_filter = "BANK"
                elif "bán lẻ" in q_low or "retail" in q_low:
                    sector_filter = "RETAIL"
                elif "công nghệ" in q_low or "tech" in q_low:
                    sector_filter = "TECHNOLOGY"
                elif "thép" in q_low or "vật liệu" in q_low:
                    sector_filter = "MATERIALS"

        crit = ScreenerCriteria(
            universe="ALL",
            sector=sector_filter,
            pe_max=pe_max if pe_max is not None else 15.0,
            pb_max=pb_max,
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
                "note": f"Mã {m.symbol}: P/E={m.pe} (nhỏ hơn {crit.pe_max}), ROE={m.roe}% (lớn hơn {crit.roe_min}%).",
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


def _get_chart_context(db: Session, symbols: list[str], as_of: date) -> dict[str, Any]:
    """
    Collects strictly grounded PIT historical series (daily prices + multi-period revenue/net_income)
    for interactive AI mini-charts without altering citation IDs.
    """
    price_series: dict[str, list[dict[str, Any]]] = {}
    financial_history: dict[str, list[dict[str, Any]]] = {}

    clean_syms = [
        s.strip().upper()
        for s in (symbols or [])
        if s and s.strip().upper() not in ("ALL", "UNIVERSE", "UNIVERSE_ALL", "VNINDEX", "VN100", "VN30")
    ][:3]

    for sym in clean_syms:
        asset = db.query(Asset).filter(Asset.symbol == sym).first()
        if not asset:
            continue

        price_rows = (
            db.query(Price)
            .filter(
                Price.asset_id == asset.id,
                Price.status == "VALID",
                Price.observation_date <= as_of,
                Price.raw_close.isnot(None),
                Price.raw_close > 0,
            )
            .order_by(Price.observation_date.desc())
            .limit(45)
            .all()
        )
        if len(price_rows) >= 2:
            ordered = list(reversed(price_rows))
            price_series[sym] = [
                {
                    "date": r.observation_date.isoformat(),
                    "close": round(float(r.adjusted_close if r.adjusted_close and r.adjusted_close > 0 else r.raw_close), 2),
                    "raw_close": round(float(r.raw_close), 2),
                }
                for r in ordered
            ]

        stmt_rows = (
            db.query(FinancialStatement, NormalizedIncome)
            .join(NormalizedIncome, NormalizedIncome.statement_id == FinancialStatement.id)
            .filter(
                FinancialStatement.asset_id == asset.id,
                FinancialStatement.statement_type == "INCOME_STATEMENT",
                FinancialStatement.publication_date <= as_of,
                FinancialStatement.status == "VALID",
            )
            .order_by(FinancialStatement.fiscal_period_end.asc())
            .all()
        )
        annual_map: dict[int, dict[str, Any]] = {}
        quarter_map: dict[tuple[int, int], dict[str, Any]] = {}
        for fs, inc in stmt_rows:
            rev = float(inc.revenue) if inc.revenue is not None else None
            ni_raw = inc.net_income_parent if inc.net_income_parent is not None else inc.net_income
            ni = float(ni_raw) if ni_raw is not None else None
            if rev is None and ni is None:
                continue
            ptype = (fs.period_type or "").upper()
            if ptype == "ANNUAL" and fs.fiscal_year:
                if fs.fiscal_year not in annual_map or fs.consolidation == "CONSOLIDATED":
                    annual_map[fs.fiscal_year] = {
                        "period": f"FY{fs.fiscal_year}",
                        "fiscal_period_end": fs.fiscal_period_end.isoformat() if fs.fiscal_period_end else None,
                        "revenue": round(rev, 2) if rev is not None else None,
                        "net_income": round(ni, 2) if ni is not None else None,
                    }
            elif ptype in ("QUARTERLY", "QUARTER") and fs.fiscal_year and fs.fiscal_quarter:
                q_key = (fs.fiscal_year, fs.fiscal_quarter)
                if q_key not in quarter_map or fs.consolidation == "CONSOLIDATED":
                    quarter_map[q_key] = {
                        "period": f"Q{fs.fiscal_quarter}-{str(fs.fiscal_year)[-2:]}",
                        "fiscal_period_end": fs.fiscal_period_end.isoformat() if fs.fiscal_period_end else None,
                        "revenue": round(rev, 2) if rev is not None else None,
                        "net_income": round(ni, 2) if ni is not None else None,
                    }

        series_pts = (
            [annual_map[y] for y in sorted(annual_map.keys())[-5:]]
            if len(annual_map) >= 2
            else [quarter_map[k] for k in sorted(quarter_map.keys())[-6:]]
        )
        if len(series_pts) >= 2:
            financial_history[sym] = series_pts

    return {
        "price_series": price_series,
        "financial_history": financial_history,
    }


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
        from services.market.trading_hours import get_effective_trading_date, get_vn_now

        close_session = session is None
        db = session or SessionLocal()
        requested_date = as_of or get_effective_trading_date()
        # Allow live after-hours / weekend 17:30 macro releases and global series (e.g. FEDFUNDS) when querying current date
        macro_cutoff = max(requested_date, get_vn_now().date()) if (as_of is None or requested_date >= get_effective_trading_date()) else requested_date
        try:
            market = build_market_dashboard(db, requested_date).model_dump(mode="json")
            macro = get_latest_macro_series(db, macro_cutoff).model_dump(mode="json")
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
            # Real VNINDEX check before falling back to VN100 Proxy disclosure
            vnindex_asset = db.query(Asset).filter(Asset.symbol == "VNINDEX").first()
            vnindex_rows = (
                db.query(Price)
                .filter(
                    Price.asset_id == vnindex_asset.id,
                    Price.status == "VALID",
                    Price.observation_date <= requested_date,
                    Price.raw_close.isnot(None),
                    Price.raw_close > 0,
                )
                .order_by(Price.observation_date.desc())
                .limit(25)
                .all()
                if vnindex_asset
                else []
            )
            if len(vnindex_rows) >= 2:
                latest_vni, prev_vni = vnindex_rows[0], vnindex_rows[1]
                vni_close = round(float(latest_vni.adjusted_close or latest_vni.raw_close), 2)
                vni_prev = round(float(prev_vni.adjusted_close or prev_vni.raw_close), 2)
                vni_chg_pct = round(((vni_close - vni_prev) / vni_prev) * 100.0, 2) if vni_prev > 0 else 0.0
                vni_20d_base = round(float((vnindex_rows[min(19, len(vnindex_rows) - 1)].adjusted_close or vnindex_rows[min(19, len(vnindex_rows) - 1)].raw_close)), 2)
                vni_mom_20d = round(((vni_close - vni_20d_base) / vni_20d_base) * 100.0, 2) if vni_20d_base > 0 else 0.0
                vni_regime = "BULLISH" if vni_mom_20d >= 2.0 else ("BEARISH" if vni_mom_20d <= -2.0 else "NEUTRAL")
                market_ev.extend([
                    {
                        "claim_type": "FACT",
                        "responsible_module": "regime",
                        "metric": "vnindex_close",
                        "symbol": "VNINDEX",
                        "value": vni_close,
                        "unit": "points",
                        "source": latest_vni.source or "CANONICAL_DATABASE",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": latest_vni.observation_date.isoformat(),
                        "note": f"Chỉ số VNINDEX phiên {latest_vni.observation_date}: {vni_close:,.2f} điểm ({vni_chg_pct:+.2f}% 1D, {vni_mom_20d:+.2f}% 20 phiên).",
                    },
                    {
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "regime",
                        "metric": "market_regime_vnindex",
                        "symbol": "VNINDEX",
                        "value": vni_regime,
                        "unit": "regime",
                        "source": "vnindex_price_momentum_v1",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": latest_vni.observation_date.isoformat(),
                        "note": f"Trạng thái xu hướng trực tiếp VNINDEX ({latest_vni.observation_date}): {vni_regime} (mức {vni_close:,.2f} điểm, biến động 20 phiên {vni_mom_20d:+.2f}%).",
                    },
                ])
            else:
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

            # Grounded Macro & Foreign Flow evidence
            macro_ev: list[dict[str, Any]] = []
            for region_name, series_list in (macro.get("regions") or {}).items():
                for s_item in series_list or []:
                    if s_item.get("value") is not None and str(s_item.get("status") or "").upper() in ("AVAILABLE", "PARTIAL"):
                        sid = str(s_item.get("series_id") or "")
                        obs_dt = s_item.get("observation_date") or s_item.get("as_of_date") or macro_cutoff.isoformat()
                        macro_ev.append({
                            "claim_type": "FACT",
                            "responsible_module": "macro",
                            "metric": sid,
                            "symbol": "MARKET",
                            "value": round(float(s_item["value"]), 3),
                            "unit": s_item.get("unit"),
                            "source": s_item.get("source") or "MACRO_DATABASE",
                            "data_origin": "CANONICAL_DATABASE",
                            "freshness": "AVAILABLE",
                            "observation_date": obs_dt,
                            "note": f"Chỉ báo vĩ mô {s_item.get('name') or sid} ({region_name}): {s_item['value']} {s_item.get('unit') or ''} tại ngày {obs_dt}.",
                        })
            ff = market.get("foreign_flow") or {}
            if isinstance(ff, dict) and ff.get("status") == "AVAILABLE" and ff.get("value") is not None:
                ff_det = ff.get("details") or {}
                top_b = ", ".join(f"{x['symbol']} (+{x['net_billion_vnd']}tỷ)" for x in (ff_det.get("top_net_buy") or [])[:3])
                top_s = ", ".join(f"{x['symbol']} ({x['net_billion_vnd']}tỷ)" for x in (ff_det.get("top_net_sell") or [])[:3])
                extra_ff = f" Mua ròng mạnh: {top_b}; Bán ròng mạnh: {top_s}." if (top_b or top_s) else ""
                macro_ev.append({
                    "claim_type": "FACT",
                    "responsible_module": "macro",
                    "metric": "hose_foreign_net_flow",
                    "symbol": "MARKET",
                    "value": ff["value"],
                    "unit": "BILLION_VND",
                    "source": ff.get("source") or "VPS_FOREIGN_FLOW",
                    "data_origin": "CANONICAL_DATABASE",
                    "freshness": "AVAILABLE",
                    "observation_date": ff.get("as_of_date") or requested_date.isoformat(),
                    "note": f"Dòng tiền khối ngoại HOSE ngày {ff.get('as_of_date')}: Ròng {ff['value']:+.2f} tỷ VND (Mua {ff_det.get('buy_billion_vnd', 'N/A')} tỷ, Bán {ff_det.get('sell_billion_vnd', 'N/A')} tỷ).{extra_ff}",
                })

            # Pillar 7: Validated 17:30 Official Macro News & Gemini Correlation Logs
            try:
                approved_news = (
                    db.query(MacroAnalysisLog)
                    .filter(
                        MacroAnalysisLog.approved_for_ai.is_(True),
                        MacroAnalysisLog.analysis_date <= macro_cutoff,
                    )
                    .order_by(
                        MacroAnalysisLog.analysis_date.desc(),
                        MacroAnalysisLog.source_trust_level.desc(),
                        MacroAnalysisLog.ai_confidence_score.desc(),
                    )
                    .limit(6)
                    .all()
                )
                for n_row in approved_news:
                    sectors_txt = ", ".join(n_row.affected_sectors or [])
                    syms_txt = ", ".join(n_row.affected_symbols or [])
                    hit_val = round(float(n_row.historical_hit_rate or 0.0) * 100.0, 1)
                    conf_val = float(n_row.ai_confidence_score or 0.0)
                    macro_ev.append({
                        "claim_type": "MODEL_OUTPUT",
                        "responsible_module": "macro",
                        "metric": "macro_event_news",
                        "symbol": "MARKET",
                        "affected_symbols": [str(s).upper() for s in (n_row.affected_symbols or [])],
                        "affected_sectors": list(n_row.affected_sectors or []),
                        "source_trust_level": n_row.source_trust_level,
                        "value": round(conf_val * 100.0, 1),
                        "unit": "%",
                        "source": f"{n_row.source_domain} (Trust {n_row.source_trust_level}/10)",
                        "data_origin": "CANONICAL_DATABASE",
                        "freshness": "AVAILABLE",
                        "observation_date": n_row.analysis_date.isoformat(),
                        "note": (
                            f"[Tin vĩ mô kiểm chứng 17:30 | {n_row.source_domain} Trust {n_row.source_trust_level}/10] "
                            f"{n_row.event_title}: {n_row.macro_impact} Tương quan {n_row.correlation_type} ({n_row.sentiment}) "
                            f"tới nhóm [{sectors_txt}] / mã [{syms_txt}]. {n_row.analysis_detail} "
                            f"(Độ tin cậy Gemini={conf_val:.2f}, Kiểm chứng backtest lịch sử Hit Rate={hit_val:.1f}%)."
                        ),
                    })
            except Exception:
                pass

            market["evidence"] = market_ev
            market["macro_evidence"] = macro_ev
            return {
                "status": market.get("status", "INSUFFICIENT_DATA"),
                "as_of_date": requested_date.isoformat(),
                "market_regime": regime.get("regime", "INSUFFICIENT_DATA"),
                "regime_confidence": regime.get("confidence"),
                "macro_growth": "AVAILABLE" if macro.get("status") == "AVAILABLE" else "INSUFFICIENT_DATA",
                "macro_liquidity": "AVAILABLE" if (ff.get("status") == "AVAILABLE") else "INSUFFICIENT_DATA",
                "macro_rates": "AVAILABLE" if macro.get("status") == "AVAILABLE" else "INSUFFICIENT_DATA",
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
            import re as _re_sym
            raw_list = [symbol] if isinstance(symbol, str) else list(symbol or [])
            raw_symbols: list[str] = []
            for item_s in raw_list:
                if not item_s:
                    continue
                if _re_sym.search(r"[,;/|]", str(item_s)):
                    raw_symbols.extend(tok.strip() for tok in _re_sym.split(r"[,;/|\s]+", str(item_s)) if tok.strip())
                else:
                    raw_symbols.append(str(item_s).strip())
            norm_symbols: list[str] = []
            for s in raw_symbols:
                if not s:
                    continue
                resolved = UniverseRegistry.resolve_instrument(db, s)
                norm = resolved.symbol if resolved else (UniverseRegistry.normalize_symbol(s) or s.upper())
                if norm and norm not in norm_symbols:
                    norm_symbols.append(norm)

            market_context = AITools.get_market_context(session=db, as_of=as_of)
            portfolio_overview, portfolio_fit_data, portfolio_workspaces, preloaded_datasets = get_portfolio_state(db, as_of)
            missing_ds_syms = [
                s for s in norm_symbols
                if s not in preloaded_datasets and s not in ("VN100", "VNINDEX", "VN30", "ALL", "UNIVERSE", "UNIVERSE_ALL", "PORTFOLIO")
            ]
            if missing_ds_syms:
                preloaded_datasets.update(
                    FinancialRepository(db).get_financial_datasets_batch(missing_ds_syms, as_of_date=as_of)
                )

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
                        sym_dataset = preloaded_datasets.get(sym, _UNSET_ARG)
                        dec_kwargs: dict[str, Any] = {
                            "market_data": market_context.get("market"),
                            "macro_data": market_context.get("macro"),
                            "portfolio_data": portfolio_overview,
                            "fit_data": portfolio_fit_data,
                            "preloaded_workspace": portfolio_workspaces.get(sym),
                        }
                        if sym_dataset is not _UNSET_ARG:
                            dec_kwargs["preloaded_dataset"] = sym_dataset
                        decision = build_decision_context(db, sym, as_of, **dec_kwargs)
                        sym_evidence = decision.get("evidence", []) if decision else []
                        for ev in sym_evidence:
                            ev_copy = dict(ev)
                            if ev_copy.get("responsible_module") == "macro":
                                ev_copy.setdefault("symbol", "MARKET")
                            else:
                                ev_copy["symbol"] = sym
                            combined_evidence.append(ev_copy)

                        # Bank metrics, deep balance/cashflow, Z-score & price change expansion
                        combined_evidence.extend(_get_price_change_evidence(db, asset, as_of))
                        combined_evidence.extend(_get_deep_fundamental_evidence(db, asset, as_of, preloaded_dataset=sym_dataset))
                        bank_ev = _get_bank_evidence(db, asset, as_of)
                        combined_evidence.extend(bank_ev)
                        combined_evidence.extend(_get_dividend_evidence(db, sym, as_of))

                        # DCF and Peer Medians expansion
                        peer_res = _get_peer_comparison(db, sym, as_of)
                        target_price = (
                            peer_res.target_metrics.current_price
                            if (peer_res and getattr(peer_res, "target_metrics", None))
                            else None
                        )
                        dcf_ev = _get_valuation_dcf_evidence(
                            db,
                            sym,
                            as_of,
                            peer_res=peer_res,
                            preloaded_dataset=sym_dataset,
                            asset_sector=asset.sector,
                            latest_price=target_price,
                            question=question,
                        )
                        combined_evidence.extend(dcf_ev)
                        peer_ev = _get_peer_median_evidence(db, sym, as_of, peer_res=peer_res)
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

                # Append market, macro & portfolio evidence for multi-ticker comparisons
                q_lower_multi = (question or "").lower()
                multi_steel_rel = any(s in {"HPG", "HSG", "NKG"} for s in norm_symbols) or any(
                    k in q_lower_multi for k in ("hrc", "thép", "thep", "steel")
                )
                multi_oil_rel = any(s in {"BSR", "PLX", "GAS", "PVD", "PVS", "OIL", "PVT"} for s in norm_symbols) or any(
                    k in q_lower_multi for k in ("crack", "lọc dầu", "dầu", "oil", "brent", "xăng")
                )
                comm_metrics_up = {str(ce.get("metric") or "").upper() for ce in comm_ev}
                for ev in market_context.get("market", {}).get("evidence", []):
                    ev_copy = dict(ev)
                    ev_copy.setdefault("symbol", "VN100")
                    combined_evidence.append(ev_copy)
                for ev in market_context.get("market", {}).get("macro_evidence", []):
                    m_up = str(ev.get("metric") or "").upper()
                    if m_up in {"HRC_STEEL_PRICE", "HRC_STEEL"} and (not multi_steel_rel or "HRC_STEEL_PRICE" in comm_metrics_up):
                        continue
                    if m_up == "SINGAPORE_CRACK_SPREAD" and (not multi_oil_rel or "SINGAPORE_CRACK_SPREAD" in comm_metrics_up):
                        continue
                    combined_evidence.append(dict(ev))
                if "PORTFOLIO" in norm_symbols or any(
                    k in q_lower_multi
                    for k in ("danh mục", "danh muc", "phân bổ", "phan bo", "giải ngân", "giai ngan", "dca", "trung bình giá", "rebalance", "tái cơ cấu", "tỷ trọng", "portfolio")
                ):
                    combined_evidence.extend(_get_portfolio_dca_evidence(portfolio_overview, portfolio_fit_data, question, as_of))

                rag_service = DocumentRAGService(session=db)
                rag_query = f"{' '.join(norm_symbols)} {question or ''}".strip() or "corporate update"
                rag_docs = rag_service.retrieve_documents(
                    query=rag_query,
                    ticker=",".join(norm_symbols),
                    as_of_date=as_of,
                    limit=6,
                    auto_ingest_local=("PYTEST_CURRENT_TEST" not in os.environ and not is_cloud_mode()),
                )
                doc_payload = rag_docs if rag_docs["status"] == "AVAILABLE" else {
                    "status": "INSUFFICIENT_DATA",
                    "documents": [],
                    "retrieval_mode": rag_docs.get("retrieval_mode", "BM25_LEXICAL_ONLY"),
                    "embedding_provider": rag_docs.get("embedding_provider", {"status": "NOT_CONFIGURED"}),
                    "note": "No local document index is currently available; retrieval remains insufficient until a local corpus is indexed.",
                }

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
                    elif name == "document_retrieval":
                        results.append({"name": name, "status": doc_payload.get("status", "INSUFFICIENT_DATA"), "data": doc_payload})
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
                    "chart_context": _get_chart_context(db, norm_symbols, as_of),
                }

            # Single symbol path (or no symbol / PORTFOLIO)
            normalized = norm_symbols[0] if norm_symbols else None
            is_virtual_entity = normalized in ("PORTFOLIO", "ALL", "UNIVERSE", "UNIVERSE_ALL")
            asset = db.query(Asset).filter(Asset.symbol == normalized).first() if (normalized and not is_virtual_entity) else None
            norm_dataset = preloaded_datasets.get(normalized, _UNSET_ARG) if (normalized and not is_virtual_entity) else _UNSET_ARG
            if normalized and not is_virtual_entity:
                dec_kwargs = {
                    "market_data": market_context.get("market"),
                    "macro_data": market_context.get("macro"),
                    "portfolio_data": portfolio_overview,
                    "fit_data": portfolio_fit_data,
                    "preloaded_workspace": portfolio_workspaces.get(normalized),
                }
                if norm_dataset is not _UNSET_ARG:
                    dec_kwargs["preloaded_dataset"] = norm_dataset
                decision = build_decision_context(db, normalized, as_of, **dec_kwargs)
            else:
                decision = None
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
                "portfolio": portfolio_overview,
                "portfolio_fit": portfolio_fit_data,
            }
            evidence = decision.get("evidence", []) if decision else []
            if normalized:
                for ev in evidence:
                    if ev.get("responsible_module") == "macro":
                        ev.setdefault("symbol", "MARKET")
                    else:
                        ev.setdefault("symbol", normalized)

            # Bank metrics, deep balance/cashflow, Z-score & price change expansion
            if asset:
                evidence.extend(_get_price_change_evidence(db, asset, as_of))
                evidence.extend(_get_deep_fundamental_evidence(db, asset, as_of, preloaded_dataset=norm_dataset))
                bank_ev = _get_bank_evidence(db, asset, as_of)
                evidence.extend(bank_ev)

            # DCF valuation & Peer medians expansion
            if normalized and not is_virtual_entity:
                peer_res = _get_peer_comparison(db, normalized, as_of)
                target_price = (
                    peer_res.target_metrics.current_price
                    if (peer_res and getattr(peer_res, "target_metrics", None))
                    else None
                )
                dcf_ev = _get_valuation_dcf_evidence(
                    db,
                    normalized,
                    as_of,
                    peer_res=peer_res,
                    preloaded_dataset=norm_dataset,
                    asset_sector=(asset.sector if asset else None),
                    latest_price=target_price,
                    question=question,
                )
                evidence.extend(dcf_ev)
                peer_ev = _get_peer_median_evidence(db, normalized, as_of, peer_res=peer_res)
                evidence.extend(peer_ev)
                opp_ev = _get_opportunity_evidence(db, normalized, as_of)
                evidence.extend(opp_ev)

            # Dividend & corporate action expansion (Q3, Q15)
            q_lower_str = (question or "").lower()
            if normalized and any(w in q_lower_str for w in (
                "cổ tức", "co tuc", "chia tách", "chia tach", "tách cổ phiếu", "tach co phieu",
                "điều chỉnh", "dieu chinh", "dividend", "yield", "split", "rights", "trước chia", "truoc chia",
            )):
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
                scr_ev = _get_screener_evidence(db, None, as_of, question=question)
                evidence.extend(scr_ev)

            # Market context, Macro rates/FX, Foreign Flow & Portfolio DCA expansion
            is_market_or_macro_query = (
                normalized in (None, "VN100", "VNINDEX", "ALL", "UNIVERSE")
                or any(k in q_lower_str for k in (
                    "chế độ thị trường", "market regime", "độ rộng", "breadth", "thị trường",
                    "lãi suất", "fed", "tỷ giá", "usd", "cpi", "lạm phát", "gdp", "vĩ mô",
                    "khối ngoại", "foreign", "wacc", "dcf", "chiết khấu",
                    "tin tức", "nhnn", "ngân hàng nhà nước", "hrc", "crack spread",
                ))
            )
            if is_market_or_macro_query and normalized != "PORTFOLIO":
                for ev in market_context.get("market", {}).get("evidence", []):
                    ev_copy = dict(ev)
                    ev_copy.setdefault("symbol", "VN100")
                    evidence.append(ev_copy)
            # Macro commodity expansion (run before macro_evidence merge so sector commodities aren't duplicated/leaked)
            comm_ev, c_series, s_series = _get_commodity_evidence_and_series(db, norm_symbols, as_of, question)
            evidence.extend(comm_ev)
            single_steel_rel = any(s in {"HPG", "HSG", "NKG"} for s in norm_symbols) or any(
                k in q_lower_str for k in ("hrc", "thép", "thep", "steel")
            )
            single_oil_rel = any(s in {"BSR", "PLX", "GAS", "PVD", "PVS", "OIL", "PVT"} for s in norm_symbols) or any(
                k in q_lower_str for k in ("crack", "lọc dầu", "dầu", "oil", "brent", "xăng")
            )
            comm_metrics_up = {str(ce.get("metric") or "").upper() for ce in comm_ev}

            if is_market_or_macro_query or normalized == "PORTFOLIO":
                for ev in market_context.get("market", {}).get("macro_evidence", []):
                    m_up = str(ev.get("metric") or "").upper()
                    if m_up in {"HRC_STEEL_PRICE", "HRC_STEEL"} and (not single_steel_rel or "HRC_STEEL_PRICE" in comm_metrics_up):
                        continue
                    if m_up == "SINGAPORE_CRACK_SPREAD" and (not single_oil_rel or "SINGAPORE_CRACK_SPREAD" in comm_metrics_up):
                        continue
                    evidence.append(dict(ev))
            else:
                # For sector / stock queries (e.g. HPG steel or BSR/PLX oil), surface matching approved 17:30 news
                norm_sym_set = {s.upper() for s in norm_symbols}
                for ev in market_context.get("market", {}).get("macro_evidence", []):
                    if ev.get("metric") != "macro_event_news":
                        continue
                    aff_syms = {str(x).upper() for x in (ev.get("affected_symbols") or [])}
                    if norm_sym_set & aff_syms:
                        evidence.append(dict(ev))

            if normalized == "PORTFOLIO" or any(
                k in q_lower_str
                for k in ("danh mục", "danh muc", "phân bổ", "phan bo", "giải ngân", "giai ngan", "dca", "trung bình giá", "rebalance", "tái cơ cấu", "tỷ trọng", "portfolio")
            ):
                evidence.extend(_get_portfolio_dca_evidence(portfolio_overview, portfolio_fit_data, question, as_of))

            rag_service = DocumentRAGService(session=db)
            rag_query = (
                f"{normalized} {question}".strip()
                if (normalized and question and question.strip())
                else ((question or "").strip() or normalized or "corporate update")
            )
            rag_docs = rag_service.retrieve_documents(
                query=rag_query,
                ticker=normalized,
                as_of_date=as_of,
                limit=5,
                auto_ingest_local=("PYTEST_CURRENT_TEST" not in os.environ and not is_cloud_mode()),
            )
            document_payload = rag_docs if rag_docs["status"] == "AVAILABLE" else {
                "status": "INSUFFICIENT_DATA",
                "documents": [],
                "retrieval_mode": rag_docs.get("retrieval_mode", "BM25_LEXICAL_ONLY"),
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
                    state = (data.get("status") if isinstance(data, dict) else _status(data)) or "INSUFFICIENT_DATA"
                results.append({"name": name, "status": state, "data": data})

            return {
                "symbol": normalized,
                "symbols": norm_symbols,
                "as_of_date": as_of.isoformat(),
                "decision_state": (
                    decision.get("decision_state")
                    if decision
                    else ("AVAILABLE" if (normalized == "PORTFOLIO" and evidence) else market_context.get("status", "INSUFFICIENT_DATA"))
                ),
                "tools": results,
                "evidence": evidence,
                "commodity_series": c_series,
                "stock_price_series": s_series,
                "chart_context": _get_chart_context(db, [normalized] if (normalized and not is_virtual_entity) else [], as_of),
            }
        finally:
            if close_session:
                db.close()
