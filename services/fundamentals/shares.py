"""
IAS 33 Time-Weighted Average Ordinary Shares Engine.

Implements deterministic Point-in-Time ordinary share denominator calculation
under IAS 33 ("Earnings per Share"):
  1. Direct statement weighted-average shares (shares_basic) when all active
     quarters/periods report them, adjusted retrospectively for post-period
     splits/stock dividends (IAS 33 para. 26 & 64).
  2. Time-weighted share timeline reconstruction across CorporateAction events
     (STOCK_SPLIT, REVERSE_SPLIT, STOCK_DIVIDEND, BONUS_ISSUE, RIGHTS_ISSUE,
     SHARE_ISSUANCE, BUYBACK) and historical share checkpoints.
  3. Explicit, non-falsified fallback to period-end outstanding shares with
     is_estimate=True when historical weighted-average evidence is absent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
import re
from typing import Any, Optional


_RETROSPECTIVE_TYPES = {"STOCK_SPLIT", "REVERSE_SPLIT", "STOCK_DIVIDEND", "BONUS_ISSUE"}
_RESOURCE_CHANGE_TYPES = {"RIGHTS_ISSUE", "SHARE_ISSUANCE", "BUYBACK"}


def _coerce_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _parse_vn_currency_amount(raw: str) -> Optional[float]:
    """Parses Vietnamese grouped currency tokens like '1.500', '2,000', or '12,500.5'."""
    tok = (raw or "").strip()
    if not tok:
        return None
    if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", tok):
        tok = tok.replace(".", "")
    elif re.fullmatch(r"\d{1,3}(?:,\d{3})+", tok):
        tok = tok.replace(",", "")
    elif "," in tok and "." in tok:
        if tok.rfind(",") > tok.rfind("."):
            tok = tok.replace(".", "").replace(",", ".")
        else:
            tok = tok.replace(",", "")
    elif "," in tok:
        parts = tok.split(",")
        tok = tok.replace(",", "") if (len(parts) > 2 or len(parts[-1]) == 3) else tok.replace(",", ".")
    try:
        return float(tok)
    except ValueError:
        return None


def _infer_quarter_start(period_end: date) -> date:
    """Infers approximate fiscal quarter start when fiscal_period_start is absent."""
    month = period_end.month
    year = period_end.year
    if month in (1, 2, 3):
        return date(year, 1, 1)
    if month in (4, 5, 6):
        return date(year, 4, 1)
    if month in (7, 8, 9):
        return date(year, 7, 1)
    return date(year, 10, 1)


def parse_corporate_action_parameters(action: dict[str, Any]) -> dict[str, Any]:
    """
    Normalizes a CorporateAction record/dict into structured financial parameters.
    Prefers explicit structured columns (`ex_date`, `ratio`, `value`) and only
    parses unstructured `notes` when explicit structured metadata is absent.
    """
    raw_type = str(action.get("action_type") or "").strip().upper()
    action_date = _coerce_date(action.get("action_date"))
    ex_date = _coerce_date(action.get("ex_date"))
    eff_date = ex_date or action_date
    has_structured_ex_date = ex_date is not None

    notes = str(action.get("notes") or "")

    raw_ratio = action.get("ratio")
    ratio_val = float(raw_ratio) if raw_ratio is not None else None
    raw_value = action.get("value")
    value_val = float(raw_value) if raw_value is not None else None

    parsed_from_notes = False
    share_multiplier: Optional[float] = None
    share_increment_ratio: Optional[float] = None
    cash_dividend_per_share: Optional[float] = None
    subscription_price: Optional[float] = None

    if raw_type in ("STOCK_DIVIDEND", "BONUS_ISSUE"):
        if ratio_val is not None and ratio_val > 0:
            if ratio_val <= 1.0:
                share_multiplier = 1.0 + ratio_val
            else:
                share_multiplier = ratio_val
        else:
            m_ratio = re.search(r"(\d+)\s*:\s*(\d+)", notes)
            m_pct = re.search(r"(\d+(?:[.,]\d+)?)\s*%", notes)
            if m_ratio:
                base_n = float(m_ratio.group(1))
                bonus_n = float(m_ratio.group(2))
                if base_n > 0 and bonus_n > 0:
                    share_multiplier = 1.0 + (bonus_n / base_n)
                    parsed_from_notes = True
            elif m_pct:
                pct = float(m_pct.group(1).replace(",", "."))
                if pct > 0:
                    share_multiplier = 1.0 + (pct / 100.0)
                    parsed_from_notes = True

    elif raw_type == "STOCK_SPLIT":
        if ratio_val is not None and ratio_val > 0:
            share_multiplier = ratio_val
        else:
            m_ratio = re.search(r"(\d+(?:[.,]\d+)?)\s*:\s*(\d+(?:[.,]\d+)?)", notes)
            if m_ratio:
                new_n = float(m_ratio.group(1).replace(",", "."))
                old_n = float(m_ratio.group(2).replace(",", "."))
                if new_n > 0 and old_n > 0:
                    share_multiplier = new_n / old_n
                    parsed_from_notes = True

    elif raw_type == "REVERSE_SPLIT":
        if ratio_val is not None and ratio_val > 0:
            share_multiplier = (1.0 / ratio_val) if ratio_val > 1.0 else ratio_val

    elif raw_type == "RIGHTS_ISSUE":
        if ratio_val is not None and ratio_val > 0:
            share_increment_ratio = ratio_val
        else:
            m_ratio = re.search(r"(\d+)\s*:\s*(\d+)", notes)
            if m_ratio:
                base_n = float(m_ratio.group(1))
                right_n = float(m_ratio.group(2))
                if base_n > 0 and right_n > 0:
                    share_increment_ratio = right_n / base_n
                    parsed_from_notes = True
        if value_val is not None and value_val > 0:
            subscription_price = value_val
        else:
            m_sub = re.search(r"(\d{1,3}(?:[.,]\d{3})+|\d[\d.,]*\d)\s*(?:đ|vnd|đồng)", notes, re.IGNORECASE)
            if m_sub:
                parsed_sub = _parse_vn_currency_amount(m_sub.group(1))
                if parsed_sub is not None and parsed_sub > 0:
                    subscription_price = parsed_sub
                    parsed_from_notes = True

    elif raw_type == "SHARE_ISSUANCE":
        if ratio_val is not None and ratio_val > 0:
            share_increment_ratio = ratio_val if ratio_val < 1.0 else (ratio_val - 1.0)

    elif raw_type == "BUYBACK":
        if ratio_val is not None and 0 < ratio_val < 1.0:
            share_increment_ratio = -ratio_val

    elif raw_type == "CASH_DIVIDEND":
        if value_val is not None and value_val > 0:
            cash_dividend_per_share = value_val
        else:
            m_cash = re.search(
                r"(\d{1,3}(?:[.,]\d{3})+|\d{3,7}(?:[.,]\d+)?)\s*(?:đ|vnd|đồng)\s*/\s*(?:cp|cổ phiếu|share)",
                notes,
                re.IGNORECASE,
            )
            if m_cash:
                parsed_cash = _parse_vn_currency_amount(m_cash.group(1))
                if parsed_cash is not None and parsed_cash > 0:
                    cash_dividend_per_share = parsed_cash
                    parsed_from_notes = True

    return {
        "action_type": raw_type,
        "action_date": action_date,
        "ex_date": ex_date,
        "effective_date": eff_date,
        "has_structured_ex_date": has_structured_ex_date,
        "parsed_from_notes": parsed_from_notes,
        "share_multiplier": share_multiplier,
        "share_increment_ratio": share_increment_ratio,
        "cash_dividend_per_share": cash_dividend_per_share,
        "subscription_price": subscription_price,
        "source": action.get("source"),
        "notes": notes,
    }


@dataclass
class WeightedSharesResult:
    symbol: str
    window_start: Optional[date]
    window_end: Optional[date]
    weighted_shares: Optional[float]
    period_end_shares: Optional[float]
    shares_basis: str
    is_estimate: bool
    diagnostic_reason: Optional[str]
    retrospective_adjustment_factor: float = 1.0
    events_applied: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "weighted_shares": round(self.weighted_shares, 2) if self.weighted_shares is not None else None,
            "period_end_shares": round(self.period_end_shares, 2) if self.period_end_shares is not None else None,
            "shares_basis": self.shares_basis,
            "is_estimate": self.is_estimate,
            "diagnostic_reason": self.diagnostic_reason,
            "retrospective_adjustment_factor": round(self.retrospective_adjustment_factor, 6),
            "events_applied": self.events_applied,
        }


class IAS33WeightedSharesEngine:
    """
    Computes IAS 33 time-weighted average ordinary shares using audited BCTC
    `shares_basic`, historical share checkpoints, and Point-in-Time CorporateActions.
    """

    @classmethod
    def compute(
        cls,
        *,
        symbol: str,
        income_quarters: list[dict[str, Any]],
        income_annual: list[dict[str, Any]],
        period_end_shares: Optional[float],
        corporate_actions: Optional[list[dict[str, Any]]] = None,
        shares_history: Optional[list[dict[str, Any]]] = None,
        as_of_date: Optional[date] = None,
        reference_prices: Optional[dict[date, float]] = None,
    ) -> WeightedSharesResult:
        sym = symbol.strip().upper()
        active_q = income_quarters[-4:] if (income_quarters and len(income_quarters) >= 4) else []

        window_start: Optional[date] = None
        window_end: Optional[date] = None
        if active_q:
            q0_end = _coerce_date(active_q[0].get("fiscal_period_end"))
            window_start = _coerce_date(active_q[0].get("fiscal_period_start")) or (
                _infer_quarter_start(q0_end) if q0_end else None
            )
            window_end = _coerce_date(active_q[-1].get("fiscal_period_end"))
        elif income_annual:
            latest_a = income_annual[-1]
            window_end = _coerce_date(latest_a.get("fiscal_period_end"))
            window_start = _coerce_date(latest_a.get("fiscal_period_start")) or (
                date(window_end.year, 1, 1) if window_end else None
            )

        cutoff_date = as_of_date or window_end

        parsed_actions: list[dict[str, Any]] = []
        for raw_ca in (corporate_actions or []):
            parsed = parse_corporate_action_parameters(raw_ca)
            eff = parsed["effective_date"]
            if eff is None:
                continue
            if cutoff_date is not None and eff > cutoff_date:
                continue
            parsed_actions.append(parsed)
        parsed_actions.sort(key=lambda x: x["effective_date"])

        retro_actions = [
            a for a in parsed_actions
            if a["action_type"] in _RETROSPECTIVE_TYPES and a["share_multiplier"] and a["share_multiplier"] > 0
        ]
        resource_actions = [
            a for a in parsed_actions
            if a["action_type"] in _RESOURCE_CHANGE_TYPES and a["share_increment_ratio"] is not None
        ]

        # Path 1: All 4 active TTM quarters (or annual if no quarters) report audited shares_basic
        if active_q and all(bool(q.get("shares_basic")) and float(q["shares_basic"]) > 0 for q in active_q):
            return cls._compute_from_audited_quarters(
                sym=sym,
                active_q=active_q,
                window_start=window_start,
                window_end=window_end,
                period_end_shares=period_end_shares,
                retro_actions=retro_actions,
            )

        if not active_q and income_annual:
            latest_a_shares = income_annual[-1].get("shares_basic")
            if latest_a_shares and float(latest_a_shares) > 0:
                base_s = float(latest_a_shares)
                retro_mult = 1.0
                applied: list[dict[str, Any]] = []
                for a in retro_actions:
                    if window_end and a["effective_date"] > window_end:
                        retro_mult *= float(a["share_multiplier"])
                        applied.append({
                            "action_type": a["action_type"],
                            "effective_date": a["effective_date"].isoformat(),
                            "multiplier": round(float(a["share_multiplier"]), 6),
                            "retrospective": True,
                            "structured": bool(a["has_structured_ex_date"] and not a["parsed_from_notes"]),
                        })
                return WeightedSharesResult(
                    symbol=sym,
                    window_start=window_start,
                    window_end=window_end,
                    weighted_shares=base_s * retro_mult,
                    period_end_shares=float(period_end_shares) if period_end_shares else base_s * retro_mult,
                    shares_basis="IAS33_AUDITED_WEIGHTED_AVG",
                    is_estimate=False,
                    diagnostic_reason=None,
                    retrospective_adjustment_factor=retro_mult,
                    events_applied=applied,
                )

        if not period_end_shares or period_end_shares <= 0:
            return WeightedSharesResult(
                symbol=sym,
                window_start=window_start,
                window_end=window_end,
                weighted_shares=None,
                period_end_shares=None,
                shares_basis="UNAVAILABLE",
                is_estimate=True,
                diagnostic_reason="NO_VERIFIED_SHARE_COUNT_AVAILABLE",
            )

        end_shares = float(period_end_shares)

        # Path 2: Time-weighted share timeline reconstruction via CorporateAction events + share checkpoints
        relevant_window_events = [
            a for a in (retro_actions + resource_actions)
            if window_start is not None and a["effective_date"] >= window_start
        ]
        prior_checkpoints = cls._collect_prior_share_checkpoints(
            window_start=window_start,
            window_end=window_end,
            income_quarters=income_quarters,
            income_annual=income_annual,
            shares_history=shares_history or [],
        )

        obs_dates = [
            dt
            for row in (shares_history or [])
            for dt in [_coerce_date(row.get("effective_date") or row.get("fiscal_period_end"))]
            if dt is not None
            and (cutoff_date is None or dt <= cutoff_date)
            and row.get("value")
            and float(row["value"]) > 0
        ]
        latest_share_obs_date = max(obs_dates) if obs_dates else None

        if (relevant_window_events or prior_checkpoints) and window_start and window_end and window_end >= window_start:
            return cls._reconstruct_from_timeline(
                sym=sym,
                window_start=window_start,
                window_end=window_end,
                end_shares=end_shares,
                retro_actions=retro_actions,
                resource_actions=resource_actions,
                prior_checkpoints=prior_checkpoints,
                reference_prices=reference_prices or {},
                latest_share_obs_date=latest_share_obs_date,
                cutoff_date=cutoff_date,
            )

        # Path 3: Honest Fallback — only period-end snapshot is available
        return WeightedSharesResult(
            symbol=sym,
            window_start=window_start,
            window_end=window_end,
            weighted_shares=end_shares,
            period_end_shares=end_shares,
            shares_basis="PERIOD_END_OUTSTANDING_FALLBACK_ESTIMATE",
            is_estimate=True,
            diagnostic_reason="WEIGHTED_AVERAGE_UNAVAILABLE_FALLBACK_TO_PERIOD_END_OUTSTANDING",
        )

    @classmethod
    def _compute_from_audited_quarters(
        cls,
        *,
        sym: str,
        active_q: list[dict[str, Any]],
        window_start: Optional[date],
        window_end: Optional[date],
        period_end_shares: Optional[float],
        retro_actions: list[dict[str, Any]],
    ) -> WeightedSharesResult:
        weighted_sum = 0.0
        total_days = 0
        applied: list[dict[str, Any]] = []
        total_retro_factor = 1.0

        for q in active_q:
            q_end = _coerce_date(q.get("fiscal_period_end"))
            q_start = _coerce_date(q.get("fiscal_period_start")) or (
                _infer_quarter_start(q_end) if q_end else None
            )
            q_days = max(1, (q_end - q_start).days + 1) if (q_start and q_end) else 91
            q_shares = float(q["shares_basic"])

            q_retro = 1.0
            if q_end:
                for ca in retro_actions:
                    if ca["effective_date"] > q_end:
                        q_retro *= float(ca["share_multiplier"])
                        applied.append({
                            "action_type": ca["action_type"],
                            "effective_date": ca["effective_date"].isoformat(),
                            "multiplier": round(float(ca["share_multiplier"]), 6),
                            "retrospective": True,
                            "applied_to_quarter_end": q_end.isoformat(),
                        })

            weighted_sum += (q_shares * q_retro) * q_days
            total_days += q_days

        if window_end:
            for ca in retro_actions:
                if ca["effective_date"] > window_end:
                    total_retro_factor *= float(ca["share_multiplier"])

        waso = weighted_sum / max(1, total_days)
        end_s = float(period_end_shares) if period_end_shares else waso
        return WeightedSharesResult(
            symbol=sym,
            window_start=window_start,
            window_end=window_end,
            weighted_shares=waso,
            period_end_shares=end_s,
            shares_basis="IAS33_AUDITED_WEIGHTED_AVG",
            is_estimate=False,
            diagnostic_reason=None,
            retrospective_adjustment_factor=total_retro_factor,
            events_applied=applied,
        )

    @staticmethod
    def _collect_prior_share_checkpoints(
        *,
        window_start: Optional[date],
        window_end: Optional[date],
        income_quarters: list[dict[str, Any]],
        income_annual: list[dict[str, Any]],
        shares_history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        checkpoints: list[dict[str, Any]] = []
        if not window_start or not window_end:
            return checkpoints

        for row in shares_history:
            dt = _coerce_date(row.get("effective_date") or row.get("fiscal_period_end"))
            val = row.get("value")
            if dt and val and float(val) > 0:
                if dt < window_end and (window_start - timedelta(days=400)) <= dt <= (window_start + timedelta(days=31)):
                    checkpoints.append({
                        "effective_date": dt,
                        "shares": float(val),
                        "source": row.get("metric_id") or "FUNDAMENTAL_METRIC",
                        "structured": True,
                    })

        for row in (income_quarters + income_annual):
            dt = _coerce_date(row.get("fiscal_period_end"))
            val = row.get("shares_basic")
            if dt and val and float(val) > 0:
                if dt < window_end and (window_start - timedelta(days=400)) <= dt <= (window_start + timedelta(days=31)):
                    checkpoints.append({
                        "effective_date": dt,
                        "shares": float(val),
                        "source": "STATEMENT_SHARES_BASIC",
                        "structured": True,
                    })

        checkpoints.sort(key=lambda c: c["effective_date"])
        return checkpoints

    @classmethod
    def _reconstruct_from_timeline(
        cls,
        *,
        sym: str,
        window_start: date,
        window_end: date,
        end_shares: float,
        retro_actions: list[dict[str, Any]],
        resource_actions: list[dict[str, Any]],
        prior_checkpoints: list[dict[str, Any]],
        reference_prices: dict[date, float],
        latest_share_obs_date: Optional[date] = None,
        cutoff_date: Optional[date] = None,
    ) -> WeightedSharesResult:
        """
        Walks backward across resource-changing events in (window_start, window_end]
        to build exact daily share regimes, while retrospectively scaling pre-event
        regimes for bonus/split events (IAS 33 para. 26 & 64).
        """
        in_window_res = [
            a for a in resource_actions
            if window_start < a["effective_date"] <= window_end
        ]
        in_window_res.sort(key=lambda x: x["effective_date"], reverse=True)

        applied_events: list[dict[str, Any]] = []
        all_structured = True
        total_retro_factor = 1.0

        for a in retro_actions:
            if window_start < a["effective_date"]:
                mult = float(a["share_multiplier"])
                total_retro_factor *= mult
                is_struct = bool(a["has_structured_ex_date"] and not a["parsed_from_notes"])
                if not is_struct:
                    all_structured = False
                applied_events.append({
                    "action_type": a["action_type"],
                    "effective_date": a["effective_date"].isoformat(),
                    "multiplier": round(mult, 6),
                    "retrospective": True,
                    "structured": is_struct,
                })

        # Note: `end_shares` may come from an observation after `window_end`
        # (`latest_share_obs_date > window_end`). If resource-changing events occurred
        # in `(window_end, latest_share_obs_date]`, undo them before entering `window_end`.
        segments: list[tuple[date, date, float]] = []
        cursor_end = window_end
        current_shares = end_shares

        def _rights_bonus_factor(ev: dict[str, Any]) -> float:
            ratio = float(ev["share_increment_ratio"])
            denom = 1.0 + ratio
            bonus = 1.0
            if ev["action_type"] == "RIGHTS_ISSUE" and ev.get("subscription_price") and ratio > 0 and denom > 0:
                eff_dt = ev["effective_date"]
                prior_ref_dates = [d for d in reference_prices if d < eff_dt and (eff_dt - d).days <= 14]
                cum_px = reference_prices[max(prior_ref_dates)] if prior_ref_dates else reference_prices.get(eff_dt)
                sub_px = float(ev["subscription_price"])
                if cum_px and cum_px > sub_px > 0:
                    terp = (cum_px + ratio * sub_px) / denom
                    if terp > 0:
                        bonus = cum_px / terp
            return bonus

        if latest_share_obs_date and latest_share_obs_date > window_end:
            post_window_res = [
                a for a in resource_actions
                if window_end < a["effective_date"] <= latest_share_obs_date
            ]
            post_window_res.sort(key=lambda x: x["effective_date"], reverse=True)
            for ev in post_window_res:
                ratio = float(ev["share_increment_ratio"])
                denom = 1.0 + ratio
                if denom <= 0:
                    continue
                is_struct = bool(ev["has_structured_ex_date"] and not ev["parsed_from_notes"])
                if not is_struct:
                    all_structured = False
                bonus_factor = _rights_bonus_factor(ev)
                current_shares = (current_shares / denom) * bonus_factor
                applied_events.append({
                    "action_type": ev["action_type"],
                    "effective_date": ev["effective_date"].isoformat(),
                    "share_increment_ratio": round(ratio, 6),
                    "bonus_factor": round(bonus_factor, 6),
                    "retrospective": False,
                    "post_window": True,
                    "structured": is_struct,
                })

        window_end_shares = current_shares

        for ev in in_window_res:
            eff_d = ev["effective_date"]
            ratio = float(ev["share_increment_ratio"])
            denom = 1.0 + ratio
            if denom <= 0:
                continue

            is_struct = bool(ev["has_structured_ex_date"] and not ev["parsed_from_notes"])
            if not is_struct:
                all_structured = False

            bonus_factor = _rights_bonus_factor(ev)

            if eff_d <= cursor_end:
                segments.append((eff_d, cursor_end, current_shares))

            # Step backward before eff_d (scaled by rights bonus element if present)
            pre_shares = (current_shares / denom) * bonus_factor
            current_shares = pre_shares
            cursor_end = eff_d - timedelta(days=1)

            applied_events.append({
                "action_type": ev["action_type"],
                "effective_date": eff_d.isoformat(),
                "share_increment_ratio": round(ratio, 6),
                "bonus_factor": round(bonus_factor, 6),
                "retrospective": False,
                "structured": is_struct,
            })

        if cursor_end >= window_start:
            segments.append((window_start, cursor_end, current_shares))

        total_days = 0
        weighted_sum = 0.0
        for seg_start, seg_end, seg_shares in segments:
            d_cnt = max(0, (seg_end - seg_start).days + 1)
            weighted_sum += seg_shares * d_cnt
            total_days += d_cnt

        waso = weighted_sum / max(1, total_days) if total_days > 0 else window_end_shares

        # Verify whether timeline is backed by corporate actions or stable share checkpoints
        has_checkpoint_stability = False
        if not in_window_res and not applied_events and prior_checkpoints:
            earliest_cp = prior_checkpoints[0]
            cp_dt = earliest_cp["effective_date"]
            cp_retro_factor = 1.0
            for a in retro_actions:
                if a["effective_date"] > cp_dt and (cutoff_date is None or a["effective_date"] <= cutoff_date):
                    cp_retro_factor *= float(a["share_multiplier"])
            # Within 0.5% of current shares (accounting for splits after checkpoint date)
            if abs((earliest_cp["shares"] * cp_retro_factor) - window_end_shares) / max(window_end_shares, 1.0) <= 0.005:
                has_checkpoint_stability = True
            else:
                return WeightedSharesResult(
                    symbol=sym,
                    window_start=window_start,
                    window_end=window_end,
                    weighted_shares=window_end_shares,
                    period_end_shares=window_end_shares,
                    shares_basis="PERIOD_END_OUTSTANDING_FALLBACK_ESTIMATE",
                    is_estimate=True,
                    diagnostic_reason="WEIGHTED_AVERAGE_UNAVAILABLE_UNEXPLAINED_SHARE_CHANGE",
                )

        has_verified_basis = (bool(in_window_res or applied_events) and all_structured) or has_checkpoint_stability
        is_estimate = not has_verified_basis
        shares_basis = (
            "IAS33_CORPORATE_ACTION_WEIGHTED_AVG"
            if has_verified_basis
            else "IAS33_CORPORATE_ACTION_WEIGHTED_AVG_ESTIMATE"
        )
        diag = None if not is_estimate else "IAS33_RECONSTRUCTED_FROM_PARTIAL_METADATA"

        return WeightedSharesResult(
            symbol=sym,
            window_start=window_start,
            window_end=window_end,
            weighted_shares=waso,
            period_end_shares=window_end_shares,
            shares_basis=shares_basis,
            is_estimate=is_estimate,
            diagnostic_reason=diag,
            retrospective_adjustment_factor=total_retro_factor,
            events_applied=applied_events,
        )
